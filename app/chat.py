import os
import streamlit as st
import pandas as pd
import json
from dotenv import load_dotenv
from pathlib import Path
from backend.audit_logger import log_query_event
import time

# Load environment
load_dotenv(dotenv_path=Path('.') / '.env', override=True)

# Local imports
from config.database_config import load_database_config
from backend.tools import (
    get_schema_map_tool,
    clear_schema_cache,
    get_schema_map_from_cache,
    list_databases,
    list_schemas
)
from backend.controller import process_user_prompt, is_destructive
from backend.sql_connector import validate_db_connection, SQLConnector

def main():
    st.title(":robot_face: SQL Database Chatbot")

    db_config = load_database_config()
    server = db_config.get("server", "")
    user = db_config.get("user", "")
    default_db = db_config.get("database")
    llm_model = os.getenv("LLM_MODEL", "Not set")

    if "selected_database" not in st.session_state:
        st.session_state.selected_database = default_db
    if "selected_schema" not in st.session_state:
        st.session_state.selected_schema = "All Schemas"
    if "full_prompt" not in st.session_state:
        st.session_state.full_prompt = ""
    if "raw_llm_output" not in st.session_state:
        st.session_state.raw_llm_output = ""
    if "generated_sql" not in st.session_state:
        st.session_state.generated_sql = ""
    if "allow_destructive" not in st.session_state:
        st.session_state.allow_destructive = False

    # --- Sidebar: Connection Settings ---
    with st.sidebar:
        st.subheader(":oil_drum: DB Connection Settings")

        previous_db = st.session_state.get("selected_database") or default_db

        available_dbs = list_databases()
        selected_db = st.selectbox("Select Database", available_dbs, index=available_dbs.index(previous_db))

        if selected_db != previous_db:
            st.session_state.selected_database = selected_db
            st.session_state.selected_schema = "All Schemas"

        available_schemas = ["All Schemas"] + list_schemas(selected_db)
        selected_schema = st.selectbox("Select Schema", available_schemas)
        st.session_state.selected_schema = selected_schema

        if st.button("🔄 Reset to Default"):
            st.session_state.selected_database = default_db
            st.session_state.selected_schema = "All Schemas"
            st.success("Reset to configured defaults.")

        if st.button("🔃 Refresh Schema Map"):
            clear_schema_cache()
            refreshed_schema = get_schema_map_tool()
            st.success("✅ Schema cache refreshed.")
            st.session_state.schema_map_refreshed = refreshed_schema.schemas

    # --- Connection Info Display ---
    with st.expander("🧠 Current Connection Info"):
        st.markdown(f"**Server:** `{server}`")
        st.markdown(f"**User:** `{user}`")
        st.markdown(f"**Database:** `{st.session_state.get('selected_database')}`")
        st.markdown(f"**LLM Model:** `{llm_model}`")
        if validate_db_connection():
            st.success("✅ Database connection verified.")
        else:
            st.error("❌ Failed to connect.")

    # --- Chat Interaction ---
    st.subheader("💬 Ask your database:")

    user_prompt = st.text_area("Enter a description of the query you want:", key="chat_user_prompt")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🛠️ Generate SQL Query"):
            if not user_prompt.strip():
                st.warning("Please enter a query description first.")
            else:
                output, raw_output, full_prompt = process_user_prompt(
                    user_prompt,
                    execute_query=False,
                    selected_database=st.session_state.selected_database  # ✅ Pass selected DB
                )
                st.session_state.generated_sql = output
                st.session_state.full_prompt = full_prompt
                st.session_state.raw_llm_output = raw_output
                st.text_area("Generated SQL:", value=output, height=200)
    with col2:
        st.checkbox(":skull: Allow Destructive Queries", key="allow_destructive")

    if st.button("▶️ Execute SQL Query"):
        sql_query = st.session_state.get("generated_sql")
        if not sql_query.strip():
            st.warning("No generated SQL to execute.")
        else:
            if is_destructive(sql_query) and not st.session_state.allow_destructive:
                st.error("Destructive SQL detected (UPDATE/DELETE) and 'Allow Destructive Queries' is OFF.")
            else:
                try:
                    start_time = time.time()

                    connector = SQLConnector(database_override=st.session_state.selected_database)  # ✅ Force DB override
                    results = connector.execute_query(sql_query)
                    connector.close_connection()

                    duration_ms = int((time.time() - start_time) * 1000)

                    log_query_event(
                        user_prompt=st.session_state.get("chat_user_prompt", ""),
                        generated_sql=sql_query,
                        success=True,
                        error_message=None,
                        execution_time_ms=duration_ms
                    )

                    if results:
                        df = pd.DataFrame(results)
                        st.subheader("📊 Query Results:")
                        st.dataframe(df)
                    else:
                        st.info("No data returned.")

                except Exception as e:
                    duration_ms = int((time.time() - start_time) * 1000)
                    log_query_event(
                        user_prompt=st.session_state.get("chat_user_prompt", ""),
                        generated_sql=sql_query,
                        success=False,
                        error_message=str(e),
                        execution_time_ms=duration_ms
                    )
                    st.error(f"Error executing query: {e}")

    # --- Debugging Expanders ---
    if st.session_state.get("full_prompt"):
        with st.expander("📝 Full Prompt Sent to LLM"):
            st.code(st.session_state.full_prompt, language="markdown")

    if st.session_state.get("raw_llm_output"):
        with st.expander("📨 Raw LLM Model Output"):
            st.code(st.session_state.raw_llm_output, language="json")

    if st.session_state.get("schema_map_refreshed"):
        with st.expander("📚 Current Schema Map (After Refresh)"):
            st.json(st.session_state.schema_map_refreshed)

if __name__ == "__main__":
    main()
