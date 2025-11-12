# app/chat.py

"""
WARNING: This module is part of a Streamlit application.
DO NOT add st.set_page_config() here - it must only be in streamlit_app.py
"""

"""
Chat Interface Module
This module handles the chat interface and database interactions.
"""

import streamlit as st
from backend.db_tools import get_databases, get_schema_map_from_cache, get_cache_path
from backend.system import test_db_connection
from backend.llm_engine import get_llm_instance, process_user_prompt
import os
from dotenv import load_dotenv
import pandas as pd
import logging
from typing import Optional
import time
import json
from pathlib import Path

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create console handler if it doesn't exist
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

def display_schema_cache_debug():
    """Display schema cache debug information in a collapsible frame."""
    with st.expander("🔧 Schema Cache Debug Info", expanded=False):
        # Get cache path
        cache_path = get_cache_path()
        st.write(f"Cache Path: {cache_path}")
        
        # Check if cache file exists
        if cache_path.exists():
            st.write("Cache Status: ✅ File exists")
            # Show file stats
            stats = cache_path.stat()
            st.write(f"Last Modified: {time.ctime(stats.st_mtime)}")
            st.write(f"File Size: {stats.st_size} bytes")
            
            # Show cache contents
            try:
                with open(cache_path, 'r') as f:
                    cache_data = json.load(f)
                st.write("Cache Contents:")
                st.json(cache_data)
            except Exception as e:
                st.error(f"Error reading cache file: {str(e)}")
        else:
            st.write("Cache Status: ❌ File does not exist")
        
        # Show session state cache
        st.write("\nSession State Cache:")
        session_cache = {k: v for k, v in st.session_state.items() if k.startswith('schema_map_')}
        if session_cache:
            st.json(session_cache)
        else:
            st.write("No schema cache in session state")

def check_configuration():
    """Check if all required configurations are set."""
    # Check database configuration
    if os.getenv("CONNECTION_MODE") == "ODBC DSN":
        required_db_vars = ["DATABASE_DSN", "DATABASE_USER", "DATABASE_PASSWORD"]
    else:  # Connection String mode
        required_db_vars = ["DATABASE_SERVER", "DATABASE_NAME", "DATABASE_USER", "DATABASE_PASSWORD"]
    
    missing_db_vars = [var for var in required_db_vars if not os.getenv(var)]
    
    if missing_db_vars:
        st.error(f"Missing database configuration: {', '.join(missing_db_vars)}")
        st.info("Please complete the configuration in the Configuration page")
        return False
    
    # Check LLM configuration
    if not get_llm_instance():
        st.error("LLM is not configured")
        st.info("Please complete the LLM configuration in the Configuration page")
        return False
    
    return True

def display_user_message(content: str):
    """Display user message with action buttons."""
    col1, col2, col3 = st.columns([0.92, 0.04, 0.04])
    with col1:
        st.markdown(content)
    with col2:
        st.button("📋", key=f"copy_{id(content)}", help="Copy to clipboard")
    with col3:
        st.button("✏️", key=f"edit_{id(content)}", help="Edit message")

def display_advanced_options():
    """Display and handle advanced chat options."""
    with st.expander("Advanced Options", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            st.checkbox("Show SQL Explanation", value=True, key="show_sql_explanation")
            st.checkbox("Show Query Plan", value=False, key="show_query_plan")
            
        with col2:
            st.checkbox("Show Row Count", value=True, key="show_row_count")
            st.checkbox("Show Execution Time", value=True, key="show_execution_time")

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
            # Process the prompt with the selected database
            response = process_user_prompt(prompt, selected_database)
            
            if response and not response.get("error"):
                # Display SQL
                with st.expander("🔍 View SQL", expanded=True):
                    st.code(response["sql"], language="sql")
                
                # Show results if available
                if response["results"]:
                    st.dataframe(pd.DataFrame(response["results"]))
            else:
                st.error(f"Error: {response.get('error', 'Unknown error occurred')}")

    except Exception as e:
        st.error(f"Error processing chat: {str(e)}")

def get_bot_response(prompt: str) -> str:
    """Get response from LLM"""
    try:
        llm = get_llm_instance()
        if not llm:
            return "Error: LLM not configured properly"
        
        # Create a placeholder for streaming output
        output_placeholder = st.empty()
        messages = []
        
        # Add initial thinking message
        st.markdown("🤔 Let me think about this...")
        time.sleep(0.5)  # Small delay to make it visible
        
        # Process the prompt
        response = process_user_prompt(prompt, os.getenv("DATABASE_NAME", ""))
        
        # Stream tool calls as they happen
        if response and "debug_info" in response and response["debug_info"].get("tool_calls"):
            st.markdown("\n**Tool Calls and Prompts:**")
            time.sleep(0.5)
            
            for tool_call in response["debug_info"]["tool_calls"]:
                # Format the tool call based on its type
                if tool_call.startswith("USER PROMPT:"):
                    st.markdown(f"\n**User Request:**\n```\n{tool_call.replace('USER PROMPT:', '').strip()}\n```")
                elif tool_call.startswith("REFINEMENT PROMPT:"):
                    st.markdown(f"\n**Refinement Request:**\n```\n{tool_call.replace('REFINEMENT PROMPT:', '').strip()}\n```")
                elif tool_call.startswith("ERROR:"):
                    st.markdown(f"\n❌ **Error:** {tool_call.replace('ERROR:', '').strip()}")
                else:
                    st.markdown(f"```\n{tool_call}\n```")
                time.sleep(0.5)  # Add a small delay to make the streaming visible
        
        # Show the initial query if available
        if response and "debug_info" in response and response["debug_info"].get("initial_query"):
            st.markdown("\n**Initial SQL Query:**")
            st.markdown(f"```sql\n{response['debug_info']['initial_query']}\n```")
            time.sleep(0.5)
        
        # Show validation error if any
        if response and "debug_info" in response and response["debug_info"].get("validation_error"):
            st.markdown(f"\n❌ **Validation Error:** {response['debug_info']['validation_error']}")
            time.sleep(0.5)
            
            # Show final query if available
            if response["debug_info"].get("final_query"):
                st.markdown("\n**Final SQL Query:**")
                st.markdown(f"```sql\n{response['debug_info']['final_query']}\n```")
                time.sleep(0.5)
        
        # Show the final response
        if response and "response" in response:
            st.markdown("\n" + response["response"])
        
        # Return the complete response for chat history
        return "\n".join([
            "🤔 Let me think about this...",
            "\n**Tool Calls and Prompts:**",
            *[tool_call for tool_call in response["debug_info"]["tool_calls"]],
            "\n**Initial SQL Query:**",
            f"```sql\n{response['debug_info']['initial_query']}\n```",
            f"\n❌ **Validation Error:** {response['debug_info']['validation_error']}" if response["debug_info"].get("validation_error") else "",
            f"\n**Final SQL Query:**\n```sql\n{response['debug_info']['final_query']}\n```" if response["debug_info"].get("final_query") else "",
            "\n" + response["response"] if response and "response" in response else ""
        ])
        
    except Exception as e:
        logger.error(f"Error in get_bot_response: {str(e)}")
        error_msg = f"Error: {str(e)}"
        st.markdown(error_msg)
        return error_msg

def main():
    st.header("🤖 SQL Chatbot")
    
    # Add debug mode toggle at the top of the page
    col1, col2 = st.columns([0.8, 0.2])
    with col2:
        st.session_state.show_llm_debug = st.checkbox("Show LLM Debug Info", value=True)
        st.session_state.show_schema_debug = st.checkbox("Show Schema Cache Debug", value=False)
    
    # Simple chat interface without advanced options
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input("Ask me about your data..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Get bot response with streaming
        with st.chat_message("assistant"):
            response = get_bot_response(prompt)
            st.session_state.messages.append({"role": "assistant", "content": response})
    
    # Show schema cache debug info if enabled
    if st.session_state.get("show_schema_debug", False):
        display_schema_cache_debug()

if __name__ == "__main__":
    main()

