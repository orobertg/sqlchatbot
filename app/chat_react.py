# app/chat_react.py

"""
WARNING: This module is part of a Streamlit application.
DO NOT add st.set_page_config() here - it must only be in streamlit_app.py
"""

import os
import streamlit as st
import pandas as pd
import json
from dotenv import load_dotenv
from pathlib import Path
import time
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import plotly.express as px

from backend.db_tools import (
    get_all_schema_names,
    validate_db_connection,
    get_schema_map,
    get_databases,
    execute_query,
    is_destructive_query,
    get_schema_map_from_cache,
    clear_schema_cache,
    format_sql_query
)

from config.database_config import load_database_config
from backend.sql_connector import validate_db_connection, SQLConnector, execute_sql_query
from backend.db_tools import clean_pretty_sql, format_sql_query
from backend.audit_logger import log_query_event, AuditLogger
from backend.system import DB_CONFIG, test_db_connection
from backend.llm_engine import (
    LocalLLM, 
    process_user_prompt, 
    extract_sql_query
)

# Important: Load environment variables at startup
# This ensures database connection parameters are available
load_dotenv()

logger = logging.getLogger(__name__)
audit_logger = AuditLogger()
llm = LocalLLM()

app = FastAPI()

class ChatRequest(BaseModel):
    prompt: str
    execute: bool = False
    database: Optional[str] = None
    schema_name: Optional[str] = None

# Ensure session state setup
st.session_state.setdefault("messages", [])
st.session_state.setdefault("llm_trace", [])
st.session_state.setdefault("sql_output", None)

def display_results(results: List[Dict[str, Any]], allow_viz: bool = True):
    """Display query results in a table with optional visualization"""
    if not results:
        st.write("No results returned")
        return
        
    if isinstance(results, str):
        if results.startswith('[') and results.endswith(']'):
            try:
                import ast
                results = ast.literal_eval(results)
            except:
                st.write(f"Error parsing results: {results}")
                return
    
    # Convert results to DataFrame
    df = pd.DataFrame(results)
    
    # Display as table
    st.dataframe(df)
    
    # Offer visualization options if enabled and data is suitable
    if allow_viz and not df.empty:
        with st.expander("📊 Visualize Data"):
            # Determine numeric and categorical columns
            numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns
            cat_cols = df.select_dtypes(include=['object', 'category']).columns
            
            if len(numeric_cols) > 0:
                # Let user choose visualization type
                viz_type = st.selectbox(
                    "Choose visualization type",
                    ["Bar Chart", "Line Chart", "Scatter Plot", "Pie Chart"],
                    key="viz_type"
                )
                
                # Let user choose columns for visualization
                if viz_type in ["Bar Chart", "Line Chart", "Pie Chart"]:
                    x_col = st.selectbox("Select X-axis", cat_cols, key="x_col")
                    y_col = st.selectbox("Select Y-axis", numeric_cols, key="y_col")
                    
                    if viz_type == "Bar Chart":
                        fig = px.bar(df, x=x_col, y=y_col)
                    elif viz_type == "Line Chart":
                        fig = px.line(df, x=x_col, y=y_col)
                    else:  # Pie Chart
                        fig = px.pie(df, names=x_col, values=y_col)
                        
                elif viz_type == "Scatter Plot" and len(numeric_cols) >= 2:
                    x_col = st.selectbox("Select X-axis", numeric_cols, key="x_col")
                    y_col = st.selectbox("Select Y-axis", numeric_cols, key="y_col")
                    fig = px.scatter(df, x=x_col, y=y_col)
                
                st.plotly_chart(fig)

def visual_query_builder():
    """Visual query builder interface"""
    with st.expander("🔍 Visual Query Builder"):
        try:
            # Create connector without parameters
            connector = SQLConnector()
            
            # Get schema information
            schema_map = get_schema_map_from_cache()
            
            if not schema_map:
                st.warning("Could not load schema information")
                return None
                
            # Let user select schema and table
            schemas = list(schema_map.keys())
            selected_schema = st.selectbox("Select Schema", schemas)
            
            if selected_schema:
                tables = list(schema_map[selected_schema]['tables'].keys())
                selected_table = st.selectbox("Select Table", tables)
                
                if selected_table:
                    # Get columns for the selected table
                    columns = schema_map[selected_schema]['tables'][selected_table]['columns']
                    column_names = [col['name'] for col in columns]
                    
                    # Let user select columns
                    selected_columns = st.multiselect("Select Columns", column_names)
                    
                    if selected_columns:
                        # Build the SQL query
                        sql = f"SELECT {', '.join(selected_columns)} FROM {selected_schema}.{selected_table}"
                        
                        # Add WHERE clause if needed
                        with st.expander("Add Filters"):
                            for col in selected_columns:
                                if st.checkbox(f"Filter {col}"):
                                    filter_value = st.text_input(f"Value for {col}")
                                    if filter_value:
                                        if "WHERE" not in sql:
                                            sql += f" WHERE {col} = '{filter_value}'"
                                        else:
                                            sql += f" AND {col} = '{filter_value}'"
                        
                        # Show the generated SQL
                        st.code(sql, language="sql")
                        return sql
            
            connector.close()
            
        except Exception as e:
            st.error(f"Error in query builder: {str(e)}")
            return None
    
    return None

def get_available_databases() -> list[str]:
    """Get list of available databases"""
    try:
        connector = SQLConnector()
        results, error = connector.execute_query("SELECT name FROM sys.databases WHERE database_id > 4")
        connector.close()
        if error or not results:
            return []
        return [row['name'] for row in results]
    except Exception as e:
        st.error(f"Error getting databases: {str(e)}")
        return []

def initialize_session_state():
    """Initialize all required session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = None
    
    if "databases" not in st.session_state:
        st.session_state.databases = []
    
    if "schema_map" not in st.session_state:
        st.session_state.schema_map = {}
    
    if "current_database" not in st.session_state:
        st.session_state.current_database = None
        
    if "chat_mode" not in st.session_state:
        st.session_state.chat_mode = "Simple"
        
    if "query_history" not in st.session_state:
        st.session_state.query_history = []
        
    if "allow_destructive" not in st.session_state:
        st.session_state.allow_destructive = False

def process_user_input(user_input: str) -> str:
    """Process user input and generate AI response."""
    try:
        # Get current schema map
        schema = get_schema_map_from_cache()
        
        # Get AI response using existing LocalLLM instance
        response = llm.get_completion(
            prompt=user_input,
            schema=schema,
            conversation_history=st.session_state.messages
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error processing user input: {str(e)}")
        return f"I apologize, but I encountered an error: {str(e)}"

def get_schema_map_from_cache(database_name=None):
    """Get schema map from cache or generate it if not present."""
    if 'schema_map' not in st.session_state:
        try:
            st.session_state.schema_map = get_schema_map()
        except Exception as e:
            st.error(f"Error getting schema map: {str(e)}")
            return {}
    
    return st.session_state.schema_map

def get_databases_from_cache():
    """Get list of databases from cache."""
    if 'databases' not in st.session_state:
        try:
            st.session_state.databases = get_databases()
        except Exception as e:
            st.error(f"Error getting databases: {str(e)}")
            return []
    
    return st.session_state.databases

def display_query_results(query: str, database: str):
    """Execute and display query results."""
    try:
        columns, results = execute_query(query, database)
        if results:
            df = pd.DataFrame(results, columns=columns)
            st.dataframe(df)
            st.caption(f"Found {len(results)} rows")
        else:
            st.info("Query executed successfully but returned no results.")
    except Exception as e:
        st.error(f"Error executing query: {str(e)}")

def display_schema_info():
    """Display database schema information."""
    schema = get_schema_map_from_cache()
    if schema:
        with st.expander("📚 Database Schema", expanded=False):
            for table_name, info in schema.items():
                st.markdown(f"### {table_name}")
                columns = info.get('columns', [])
                
                # Create a DataFrame for better column display
                column_data = []
                for col in columns:
                    column_data.append({
                        "Column": col['name'],
                        "Type": col['type'],
                        "PK": "✓" if col.get('is_primary_key') else "",
                        "FK": "✓" if col.get('is_foreign_key') else ""
                    })
                
                if column_data:
                    st.dataframe(
                        pd.DataFrame(column_data),
                        hide_index=True,
                        use_container_width=True
                    )

def process_chat(prompt: str):
    """Process the chat prompt and display the response"""
    try:
        # Check if we have a valid database connection
        db_success, _ = test_db_connection()
        if not db_success:
            st.error("Please verify your database configuration in the Configuration page")
            return

        # Get the current database from environment or configuration
        selected_database = os.getenv("DATABASE_NAME", "")
        if not selected_database:
            st.error("Database name not configured. Please check your configuration.")
            return

        with st.spinner("Thinking..."):
            response = process_user_prompt(prompt, selected_database)
            
            if response and not response.get("error"):
                # Display SQL
                with st.expander("🔍 View SQL", expanded=True):
                    st.code(response["sql"], language="sql")
                
                # Show results if available
                if response["results"]:
                    st.dataframe(pd.DataFrame(response["results"]))
            else:
                # Display detailed error message
                st.markdown(response["response"])
                
                # Show debug info if available
                if response.get("debug_info"):
                    with st.expander("Debug Information", expanded=False):
                        st.json(response["debug_info"])

    except Exception as e:
        st.error(f"Error processing chat: {str(e)}")

def main():
    st.header("🤖 SQL Chatbot (Advanced Mode)")
    
    # Initialize session state for advanced options
    if "show_advanced" not in st.session_state:
        st.session_state.show_advanced = False
        
    # Advanced options toggle
    with st.expander("⚙️ Advanced Options", expanded=st.session_state.show_advanced):
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.include_schema = st.checkbox(
                "Include schema information",
                value=st.session_state.get("include_schema", True),
                help="Include table structure in context"
            )
            st.session_state.allow_destructive = st.checkbox(
                "Allow destructive queries",
                value=st.session_state.get("allow_destructive", False),
                help="Enable INSERT, UPDATE, DELETE operations"
            )
        with col2:
            st.session_state.include_samples = st.checkbox(
                "Include sample data",
                value=st.session_state.get("include_samples", True),
                help="Include sample data in context"
            )
    
    # Initialize session state
    initialize_session_state()
    
    try:
        # Get available databases
        databases = get_databases_from_cache()
        
        # Mode selector using toggle
        advanced_mode = st.toggle(
            "Advanced Mode",
            value=st.session_state.chat_mode == "Advanced",
            help="Toggle between simple and advanced chat interface"
        )
        st.session_state.chat_mode = "Advanced" if advanced_mode else "Simple"
        
        if databases:
            # Database selector
            selected_db = st.selectbox(
                "Select Database",
                options=databases,
                index=databases.index(st.session_state.current_database) if st.session_state.current_database in databases else 0
            )
            
            if selected_db != st.session_state.current_database:
                st.session_state.current_database = selected_db
                st.session_state.schema_map = get_schema_map()
        
        # Display schema in Advanced mode
        if advanced_mode:
            display_schema_info()
        
        # Display chat messages
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                
                # In Advanced mode, handle SQL queries
                if advanced_mode and message["role"] == "assistant":
                    query = extract_sql_query(message["content"])
                    if query:
                        with st.expander("🔍 View Query and Results", expanded=True):
                            # Show editable query
                            edited_query = st.text_area("SQL Query", value=query)
                            
                            # Execute button
                            if st.button("▶️ Execute Query"):
                                display_query_results(edited_query,database=st.session_state.current_database)
                                
                                # Add to query history
                                st.session_state.query_history.append({
                                    "query": edited_query,
                                    "timestamp": pd.Timestamp.now()
                                })
        
        # Chat input
        if prompt := st.chat_input("What would you like to know about the database?"):
            # Add user message to chat history
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Get AI response
            with st.chat_message("assistant"):
                response = process_user_input(prompt)
                st.markdown(response)
                
                # In Advanced mode, handle SQL queries
                if advanced_mode:
                    query = extract_sql_query(response)
                    if query:
                        with st.expander("🔍 View Query and Results", expanded=True):
                            # Show editable query
                            edited_query = st.text_area("SQL Query", value=query)
                            
                            # Execute button
                            if st.button("▶️ Execute Query"):
                                display_query_results(edited_query, database=st.session_state.current_database)
                                
                                # Add to query history
                                st.session_state.query_history.append({
                                    "query": edited_query,
                                    "timestamp": pd.Timestamp.now()
                                })
                
            # Add AI response to chat history
            st.session_state.messages.append({"role": "assistant", "content": response})
        
        # Display query history in Advanced mode
        if advanced_mode and st.session_state.query_history:
            with st.expander("📜 Query History", expanded=False):
                for item in reversed(st.session_state.query_history):
                    st.code(item["query"], language="sql")
                    st.caption(f"Executed at: {item['timestamp']}")
                    st.divider()
    
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        logger.error(f"Error in chat interface: {str(e)}")

if __name__ == "__main__":
    main()
