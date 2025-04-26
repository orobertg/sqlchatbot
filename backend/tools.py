import logging
from pydantic import BaseModel, Field
from typing import Optional, Any
from sqlalchemy import create_engine, text
from config.database_config import load_database_config
import streamlit as st

logging.basicConfig(level=logging.INFO)

SCHEMA_CACHE = {}

def get_engine():
    config = load_database_config()
    driver = config.get("driver", "")
    server = config.get("server", "")
    port = config.get("port", "1433")

    # Use session selected database if available
    database = st.session_state.get("selected_database") or config.get("database", "")
    user = config.get("user", "")
    password = config.get("password", "")

    if server.startswith("tcp:"):
        server = server.replace("tcp:", "")

    driver_fmt = driver.replace("{", "").replace("}", "").replace(" ", "+")
    conn_str = f"mssql+pyodbc://{user}:{password}@{server},{port}/{database}?driver={driver_fmt}"
    logging.info("[get_engine] Using connection string (safe): %s", conn_str.replace(password, "*****"))
    return create_engine(conn_str)

def clear_schema_cache():
    global SCHEMA_CACHE
    SCHEMA_CACHE = {}
    logging.info("[SchemaCache] Cleared schema cache.")

def get_schema_map_tool():
    global SCHEMA_CACHE
    config = load_database_config()
    current_db = st.session_state.get("selected_database") or config.get("database", "").strip()

    if SCHEMA_CACHE and SCHEMA_CACHE.get("database_name") == current_db:
        logging.info("[SchemaCache] Using cached schema map for DB: %s", current_db)
        return SchemaMapOutput(schemas=SCHEMA_CACHE["schemas"])

    logging.info("[SchemaCache] Rebuilding schema map for new database: %s", current_db)
    query = """
        SELECT TABLE_SCHEMA, TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE = 'BASE TABLE'
    """

    with get_engine().connect() as conn:
        result = conn.execute(text(query))
        schema_map = {}
        for row in result:
            schema_map.setdefault(row[0], []).append(row[1])

    SCHEMA_CACHE = {
        "database_name": current_db,
        "schemas": schema_map
    }
    logging.info("[SchemaCache] Cached schema map: %s", schema_map)

    return SchemaMapOutput(schemas=schema_map)

def get_schema_map_from_cache() -> dict:
    """
    Returns the cached schema map directly if available.
    Forces rebuild if cache is empty.
    """
    return get_schema_map_tool().schemas

def list_databases() -> list:
    query = "SELECT name FROM sys.databases;"
    with get_engine().connect() as conn:
        result = conn.execute(text(query))
        return [row[0] for row in result]

def list_schemas(database=None) -> list:
    """
    List distinct schemas in the selected database.
    """
    database = database or st.session_state.get("selected_database") or load_database_config().get("database")
    query = f"""
        SELECT DISTINCT TABLE_SCHEMA
        FROM [{database}].INFORMATION_SCHEMA.TABLES
    """
    with get_engine().connect() as conn:
        result = conn.execute(text(query))
        return [row[0] for row in result]

# --- Pydantic Input/Output Models ---

class ListTablesInput(BaseModel):
    schema_name: Optional[str] = Field(None)

class ListTablesOutput(BaseModel):
    tables: list[str]

class DescribeTableInput(BaseModel):
    table_name: str
    schema_name: Optional[str] = Field(None)

class DescribeTableOutput(BaseModel):
    columns: list[dict[str, Any]]

class ExecuteQueryInput(BaseModel):
    query: str

class ExecuteQueryOutput(BaseModel):
    rows: list[dict[str, Any]]

class SchemaMapOutput(BaseModel):
    schemas: dict[str, list[str]]

# --- Tool Functions ---

def list_tables(input: ListTablesInput) -> ListTablesOutput:
    with get_engine().connect() as conn:
        if input.schema_name:
            query = """
                SELECT TABLE_SCHEMA + '.' + TABLE_NAME AS TABLE_NAME 
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA = :schema_name
            """
            result = conn.execute(text(query), {"schema_name": input.schema_name})
        else:
            query = """
                SELECT TABLE_SCHEMA + '.' + TABLE_NAME AS TABLE_NAME 
                FROM INFORMATION_SCHEMA.TABLES
            """
            result = conn.execute(text(query))
        tables = [row[0] for row in result]
    logging.info("[list_tables] Tables: %s", tables)
    return ListTablesOutput(tables=tables)

def describe_table(input: DescribeTableInput) -> DescribeTableOutput:
    if input.schema_name:
        schema = input.schema_name
        table = input.table_name
    else:
        if '.' in input.table_name:
            schema, table = input.table_name.split('.', 1)
        else:
            schema = "dbo"
            table = input.table_name

    query = """
        SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = :schema 
        AND TABLE_NAME = :table
    """
    with get_engine().connect() as conn:
        result = conn.execute(text(query), {"schema": schema, "table": table})
        columns = [
            {"COLUMN_NAME": row[0], "DATA_TYPE": row[1], "MAX_LENGTH": row[2]}
            for row in result
        ]
    logging.info("[describe_table] %s.%s columns: %s", schema, table, columns)
    return DescribeTableOutput(columns=columns)

def execute_query(input: ExecuteQueryInput) -> ExecuteQueryOutput:
    with get_engine().connect() as conn:
        result = conn.execute(text(input.query))
        keys = result.keys()
        rows = [dict(zip(keys, row)) for row in result.fetchall()]
    logging.info("[execute_query] %d rows returned", len(rows))
    return ExecuteQueryOutput(rows=rows)
