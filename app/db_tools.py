import time
import logging
import streamlit as st
import pandas as pd
from config.database_config import load_database_config
from backend.sql_connector import SQLConnector
from backend.tools import list_databases, list_schemas
from backend.audit_logger import log_query_event  # ⬅️ Add this near your imports
import time 

def list_tables_with_columns(database: str = None, schema: str = None, retries: int = 3, delay: int = 2):
    database = database or st.session_state.get("selected_database") or load_database_config().get("database")
    schema = schema or st.session_state.get("selected_schema")

    query = f"""
        SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME
        FROM [{database}].INFORMATION_SCHEMA.COLUMNS
    """
    if schema and schema != "All Schemas":
        query += f" WHERE TABLE_SCHEMA = '{schema}'"

    attempt = 0
    while attempt < retries:
        try:
            connector = SQLConnector()
            results = connector.execute_query(query)
            connector.close_connection()
            output = {}
            for row in results:
                full_table = f"{row[0]}.{row[1]}"
                output.setdefault(full_table, []).append(row[2])
            return output
        except Exception as e:
            logging.error(f"Error listing tables and columns: {e}")
            attempt += 1
            time.sleep(delay)
    raise Exception(f"Failed to list tables/columns after multiple retries.")

def execute_sql_query(query: str):
    try:
        connector = SQLConnector()
        results = connector.execute_query(query)
        connector.close_connection()
        return results
    except Exception as e:
        logging.error(f"Error executing query: {e}")
        return None

def main():
    st.title("🛠️ Database Tools")

    db_config = load_database_config()
    default_db = db_config.get("database")

    if "selected_database" not in st.session_state:
        st.session_state.selected_database = default_db
    if "selected_schema" not in st.session_state:
        st.session_state.selected_schema = None

    with st.sidebar:
        st.subheader(":oil_drum: DB Connection Settings")

        previous_db = st.session_state.get("selected_database") or default_db
        available_dbs = list_databases()
        selected_db = st.selectbox("Select Database", available_dbs, index=available_dbs.index(previous_db))

        if selected_db != previous_db:
            st.session_state.selected_database = selected_db
            st.session_state.selected_schema = None  # Reset schema if DB changes

        available_schemas = list_schemas(selected_db)
        selected_schema = st.selectbox("Select Schema", available_schemas)
        st.session_state.selected_schema = selected_schema

        if st.button("🔄 Reset to Default"):
            st.session_state.selected_database = default_db
            st.session_state.selected_schema = None
            st.success("Reset to configured defaults.")

    # --- Table and Columns Viewer ---
    st.subheader(f"📚 Tables and Columns in {st.session_state.selected_database} / {st.session_state.selected_schema or 'All Schemas'}")

    try:
        tables = list_tables_with_columns()
        with st.expander("📦 View Tables and Columns"):
            st.json(tables)
    except Exception as e:
        st.error(f"Error loading tables and columns: {e}")

    # --- SQL Query Box ---
    st.subheader("💬 Manual SQL Query Execution")

    sql_query = st.text_area("Enter SQL query here:", height=200)

    if st.button("▶️ Execute Query"):
        if not sql_query.strip():
            st.warning("Please enter a query first.")
        else:
            try:
                start_time = time.time()

                results = execute_sql_query(sql_query)

                duration_ms = int((time.time() - start_time) * 1000)

                # ✅ Log success
                log_query_event(
                    user_prompt="Manual Query from db_tools",
                    generated_sql=sql_query,
                    success=True,
                    execution_time_ms=duration_ms
                )

                if results:
                    df = pd.DataFrame(results)
                    st.dataframe(df)
                else:
                    st.info("No data returned.")

            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                log_query_event(
                    user_prompt="Manual Query from db_tools",
                    generated_sql=sql_query,
                    success=False,
                    error_message=str(e),
                    execution_time_ms=duration_ms
                )
                st.error(f"Error executing query: {e}")