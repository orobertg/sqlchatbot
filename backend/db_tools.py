"""
Database Tools Module
Handles database operations and schema information
"""

import logging
import re
from typing import Dict, List, Optional, Tuple, Any, Union
from pydantic import BaseModel, Field
from pathlib import Path
import json
import time
import sqlalchemy as sa
import sqlparse
from sqlparse.sql import Identifier
import pyodbc
from backend.system import DB_CONFIG
from functools import lru_cache
from backend.sql_connector import SQLConnector
from enum import Enum
from sqlglot import parse_one, exp
from sqlglot.schema import MappingSchema
import streamlit as st

logger = logging.getLogger(__name__)

# Cache settings
CACHE_DIR = Path("data/cache")
CACHE_DURATION = 7200  # 2 hours in seconds

# --- Pydantic Models ---
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

class DatabaseType(Enum):
    """Supported database types."""
    MSSQL = "mssql"
    MYSQL = "mysql"
    POSTGRES = "postgres"
    SQLITE = "sqlite"

# --- Schema Cache Functions ---
def clear_all_caches():
    """Clear all schema and table related caches"""
    logger.info("Clearing all schema and table caches")
    try:
        # Clear schema cache
        clear_schema_cache()
        # Clear table description cache
        clear_table_cache()
        logger.info("Successfully cleared all caches")
        return True
    except Exception as e:
        logger.error(f"Error clearing caches: {str(e)}")
        return False

def clear_schema_cache():
    """Clear the schema cache"""
    logger.info("Clearing schema cache")
    
    # Clear session state cache
    for key in list(st.session_state.keys()):
        if key.startswith('schema_map_'):
            del st.session_state[key]
    
    # Clear file cache
    try:
        for cache_file in CACHE_DIR.glob("*_schema.json"):
            cache_file.unlink()
    except Exception as e:
        logger.error(f"Error clearing cache files: {str(e)}")

def get_cache_path(database: str = None) -> Path:
    """Get cache file path for database"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe_db_name = database.replace('/', '_').replace('\\', '_') if database else 'default'
    return CACHE_DIR / f"{safe_db_name}_schema.json"

def is_cache_valid(cache_path: Path) -> bool:
    """Check if cache is still valid"""
    if not cache_path.exists():
        return False
    return time.time() - cache_path.stat().st_mtime < CACHE_DURATION

def get_schema_map_from_cache(database: str = None) -> Dict:
    """Get schema map from cache or build it"""
    try:
        cache_path = get_cache_path(database)
        logger.info(f"Attempting to get schema map from cache. Cache path: {cache_path}")
        
        # Check session state first for faster access
        cache_key = f"schema_map_{database or 'default'}"
        if cache_key in st.session_state:
            logger.info("Using schema map from session state")
            return st.session_state[cache_key]
        
        # If not in session state, try file cache
        if is_cache_valid(cache_path):
            logger.info("Cache is valid, reading from cache file")
            with open(cache_path, 'r') as f:
                schema_map = json.load(f)
                # Store in session state for faster access
                st.session_state[cache_key] = schema_map
                logger.info(f"Successfully loaded schema map from cache with {len(schema_map)} schemas")
                return schema_map
                
        # If no valid cache exists, build new schema map
        logger.info("Cache is invalid or doesn't exist, building new schema map")
        schema_map = _build_schema_map(database)
        
        if not schema_map:
            logger.error("Failed to build schema map - returned empty dictionary")
            return {}
            
        logger.info(f"Successfully built schema map with {len(schema_map)} schemas")
        
        # Save to file cache
        try:
            with open(cache_path, 'w') as f:
                json.dump(schema_map, f)
            # Store in session state for faster access
            st.session_state[cache_key] = schema_map
            logger.info("Successfully saved schema map to cache")
        except Exception as e:
            logger.error(f"Failed to save schema map to cache: {str(e)}")
            
        return schema_map
        
    except Exception as e:
        logger.error(f"Error getting schema map from cache: {str(e)}")
        return {}

def _build_schema_map(database: str = None) -> Dict:
    """
    Build schema map for the specified database.
    
    Args:
        database (str, optional): Database name. If None, uses current database.
        
    Returns:
        Dict: Schema map containing tables and columns
    """
    try:
        logger.info(f"Building schema map for database: {database}")
        schema_map = {}
        
        # Test database connection first
        if not validate_db_connection():
            logger.error("Database connection validation failed")
            return {}
            
        # Get all schemas
        schema_query = """
        SELECT DISTINCT s.name as schema_name
        FROM sys.schemas s
        WHERE s.name NOT IN ('sys', 'INFORMATION_SCHEMA')
        ORDER BY s.name;
        """
        logger.info("Executing schema query...")
        schemas = execute_query(schema_query, database)
        # Convert pyodbc.Row to dict if needed
        schemas = [dict(row) if hasattr(row, 'keys') and hasattr(row, '__getitem__') else row for row in schemas]
        if not schemas:
            logger.error("No schemas returned from database")
            return {}
            
        logger.info(f"Found {len(schemas)} schemas: {[s['schema_name'] for s in schemas]}")
        
        for schema in schemas:
            schema_name = schema['schema_name']
            logger.info(f"\nProcessing schema: {schema_name}")
            schema_map[schema_name] = {"tables": {}}
            
            # Get all tables in the schema
            table_query = f"""
            SELECT t.name as table_name
            FROM sys.tables t
            INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
            WHERE s.name = '{schema_name}'
            ORDER BY t.name;
            """
            logger.info(f"Executing table query for schema {schema_name}...")
            tables = execute_query(table_query, database)
            tables = [dict(row) if hasattr(row, 'keys') and hasattr(row, '__getitem__') else row for row in tables]
            if not tables:
                logger.warning(f"No tables found in schema {schema_name}")
                continue
                
            logger.info(f"Found {len(tables)} tables in schema {schema_name}: {[t['table_name'] for t in tables]}")
            
            for table in tables:
                table_name = table['table_name']
                logger.info(f"\nProcessing table: {schema_name}.{table_name}")
                schema_map[schema_name]["tables"][table_name] = {
                    "columns": {},
                    "primary_keys": [],
                    "foreign_keys": []
                }
                
                # Get columns
                column_query = f"""
                SELECT 
                    c.name as column_name,
                    t.name as data_type,
                    c.is_nullable,
                    c.is_identity,
                    c.max_length,
                    c.precision,
                    c.scale
                FROM sys.columns c
                INNER JOIN sys.types t ON c.user_type_id = t.user_type_id
                INNER JOIN sys.tables tab ON c.object_id = tab.object_id
                INNER JOIN sys.schemas s ON tab.schema_id = s.schema_id
                WHERE s.name = '{schema_name}'
                AND tab.name = '{table_name}'
                ORDER BY c.column_id;
                """
                logger.info(f"Executing column query for {schema_name}.{table_name}...")
                columns = execute_query(column_query, database)
                columns = [dict(row) if hasattr(row, 'keys') and hasattr(row, '__getitem__') else row for row in columns]
                if not columns:
                    logger.warning(f"No columns found for table {schema_name}.{table_name}")
                    continue
                    
                logger.info(f"Found {len(columns)} columns in {schema_name}.{table_name}")
                
                for column in columns:
                    schema_map[schema_name]["tables"][table_name]["columns"][column['column_name']] = {
                        "type": column['data_type'],
                        "nullable": column['is_nullable'],
                        "identity": column['is_identity'],
                        "max_length": column['max_length'],
                        "precision": column['precision'],
                        "scale": column['scale']
                    }
                
                # Get primary keys
                pk_query = f"""
                SELECT c.name as column_name
                FROM sys.indexes i
                INNER JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
                INNER JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
                INNER JOIN sys.tables t ON i.object_id = t.object_id
                INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
                WHERE i.is_primary_key = 1
                AND s.name = '{schema_name}'
                AND t.name = '{table_name}'
                ORDER BY ic.key_ordinal;
                """
                logger.info(f"Executing primary key query for {schema_name}.{table_name}...")
                primary_keys = execute_query(pk_query, database)
                primary_keys = [dict(row) if hasattr(row, 'keys') and hasattr(row, '__getitem__') else row for row in primary_keys]
                schema_map[schema_name]["tables"][table_name]["primary_keys"] = [pk['column_name'] for pk in primary_keys]
                logger.info(f"Found {len(primary_keys)} primary keys in {schema_name}.{table_name}")
                
                # Get foreign keys
                fk_query = f"""
                SELECT 
                    fk.name as fk_name,
                    c.name as column_name,
                    OBJECT_SCHEMA_NAME(fk.referenced_object_id) as referenced_schema,
                    OBJECT_NAME(fk.referenced_object_id) as referenced_table,
                    COL_NAME(fk.referenced_object_id, fkc.referenced_column_id) as referenced_column
                FROM sys.foreign_keys fk
                INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
                INNER JOIN sys.columns c ON fkc.parent_object_id = c.object_id AND fkc.parent_column_id = c.column_id
                INNER JOIN sys.tables t ON fk.parent_object_id = t.object_id
                INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
                WHERE s.name = '{schema_name}'
                AND t.name = '{table_name}'
                ORDER BY fk.name, fkc.constraint_column_id;
                """
                logger.info(f"Executing foreign key query for {schema_name}.{table_name}...")
                foreign_keys = execute_query(fk_query, database)
                foreign_keys = [dict(row) if hasattr(row, 'keys') and hasattr(row, '__getitem__') else row for row in foreign_keys]
                schema_map[schema_name]["tables"][table_name]["foreign_keys"] = [
                    {
                        "column": fk['column_name'],
                        "references": f"{fk['referenced_schema']}.{fk['referenced_table']}.{fk['referenced_column']}"
                    }
                    for fk in foreign_keys
                ]
                logger.info(f"Found {len(foreign_keys)} foreign keys in {schema_name}.{table_name}")
        
        if not schema_map:
            logger.error("No schema information was built")
            return {}
            
        logger.info("\nFinal schema map structure:")
        for schema_name, schema_info in schema_map.items():
            logger.info(f"\nSchema: {schema_name}")
            for table_name, table_info in schema_info["tables"].items():
                logger.info(f"  Table: {table_name}")
                logger.info(f"    Columns: {list(table_info['columns'].keys())}")
                logger.info(f"    Primary Keys: {table_info['primary_keys']}")
                logger.info(f"    Foreign Keys: {[fk['column'] for fk in table_info['foreign_keys']]}")
        
        return schema_map
        
    except Exception as e:
        logger.error(f"Error building schema map: {str(e)}")
        raise

# --- Tool Functions ---
def list_tables(input: ListTablesInput) -> ListTablesOutput:
    """List tables in the database."""
    try:
        connector = SQLConnector()
        if input.schema_name:
            query = """
                SELECT TABLE_SCHEMA + '.' + TABLE_NAME AS TABLE_NAME
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA = ?
            """
            columns, results = connector.execute_query(query, params=[input.schema_name])
        else:
            query = """
                SELECT TABLE_SCHEMA + '.' + TABLE_NAME AS TABLE_NAME 
                FROM INFORMATION_SCHEMA.TABLES
            """
            columns, results = connector.execute_query(query)
            
        # Handle the results properly - results is a list of tuples
        tables = []
        if results:
            for row in results:
                if isinstance(row, (list, tuple)) and len(row) > 0:
                    tables.append(row[0])
                elif isinstance(row, dict):
                    tables.append(row.get('TABLE_NAME'))
                    
        logger.info("[list_tables] Tables: %s", tables)
        return ListTablesOutput(tables=tables)
    finally:
        connector.close()

def describe_table(table_name: str, schema_name: str = 'dbo', connector: Optional[SQLConnector] = None) -> Dict:
    """
    Get table description including columns and their properties.
    """
    try:
        should_close = False
        if connector is None:
            connector = SQLConnector()
            should_close = True
            
        query = """
        SELECT 
            c.name AS column_name,
            t.name AS data_type,
            c.is_nullable,
            CASE WHEN pk.column_id IS NOT NULL THEN 1 ELSE 0 END AS is_primary_key,
            CASE WHEN fk.parent_column_id IS NOT NULL THEN 1 ELSE 0 END AS is_foreign_key
        FROM sys.columns c
        JOIN sys.types t ON c.user_type_id = t.user_type_id
        JOIN sys.tables tbl ON c.object_id = tbl.object_id
        JOIN sys.schemas s ON tbl.schema_id = s.schema_id
        LEFT JOIN sys.index_columns pk 
            JOIN sys.indexes i ON pk.object_id = i.object_id 
            AND pk.index_id = i.index_id AND i.is_primary_key = 1
            ON c.object_id = pk.object_id AND c.column_id = pk.column_id
        LEFT JOIN sys.foreign_key_columns fk ON c.object_id = fk.parent_object_id 
            AND c.column_id = fk.parent_column_id
        WHERE tbl.name = ? AND s.name = ?
        ORDER BY c.column_id
        """
        
        _, results = connector.execute_query(query, params=[table_name, schema_name])

        if should_close:
            connector.close()

        if not results:
            logger.warning(f"No results for table {schema_name}.{table_name}")
            return None

        columns = []
        for row in results:
            column_data = {
                'name': row['column_name'],
                'type': row['data_type'],
                'is_nullable': bool(row['is_nullable']),
                'is_primary_key': bool(row['is_primary_key']),
                'is_foreign_key': bool(row['is_foreign_key'])
            }
            columns.append(column_data)
            
        if not columns:
            logger.warning(f"No columns found for table {schema_name}.{table_name}")
            return None
            
        logger.info(f"Successfully described table {schema_name}.{table_name} with {len(columns)} columns")
        return {
            'columns': columns
        }
        
    except Exception as e:
        logger.error(f"Error describing table {schema_name}.{table_name}: {str(e)}")
        return None

def is_destructive_query(sql: str) -> bool:
    """Check if SQL query is destructive (modifies data)"""
    if not sql:
        return False
    destructive_keywords = {'INSERT', 'UPDATE', 'DELETE', 'DROP', 'TRUNCATE', 'ALTER'}
    sql_upper = sql.upper()
    return any(keyword in sql_upper for keyword in destructive_keywords)

def validate_db_connection() -> bool:
    """
    Validate database connection.
    
    Returns:
        bool: True if connection is valid, False otherwise
    """
    try:
        connector = SQLConnector()
        connector.close()
        return True
    except Exception as e:
        logger.error(f"Database connection validation failed: {str(e)}")
        return False

def execute_query(query_or_input: Union[str, ExecuteQueryInput], database: str = None) -> Union[ExecuteQueryOutput, List[Dict]]:
    """
    Execute a SQL query and return results as dictionaries.
    
    Args:
        query_or_input (Union[str, ExecuteQueryInput]): Either a query string or ExecuteQueryInput object
        database (str, optional): Database name to use for the query
        
    Returns:
        Union[ExecuteQueryOutput, List[Dict]]: Query results as list of dictionaries
    """
    try:
        # Handle both string queries and ExecuteQueryInput objects
        if isinstance(query_or_input, ExecuteQueryInput):
            query = query_or_input.query
            return_type = "ExecuteQueryOutput"
        else:
            query = query_or_input
            return_type = "List[Dict]"
            
        connector = SQLConnector(database=database)
        columns, results = connector.execute_query(query)
        
        # Convert results to list of dictionaries
        rows = []
        if results:
            for row in results:
                if isinstance(row, (list, tuple)):
                    row_dict = dict(zip(columns, row))
                elif isinstance(row, dict):
                    row_dict = row
                elif hasattr(row, 'keys') and hasattr(row, '__getitem__'):
                    # Likely a pyodbc.Row
                    row_dict = {k: row[k] for k in row.keys()}
                else:
                    logger.warning(f"Unexpected row type: {type(row)}")
                    continue
                rows.append(row_dict)
        
        logger.info("[execute_query] %d rows returned", len(rows))
        
        # Return appropriate type based on input
        if return_type == "ExecuteQueryOutput":
            return ExecuteQueryOutput(rows=rows)
        return rows
        
    except Exception as e:
        logger.error(f"Error executing query: {str(e)}")
        raise
    finally:
        connector.close()

def get_databases() -> List[str]:
    """
    Get list of available databases (excluding system databases).
    
    Returns:
        List[str]: List of database names
    """
    try:
        connector = SQLConnector()
        query = "SELECT name FROM sys.databases WHERE database_id > 4;"  # Skip system DBs
        _, results = connector.execute_query(query)
        connector.close()
        return [row['name'] for row in results] if results else []
    except Exception as e:
        logger.error(f"Error getting databases: {str(e)}")
        return []

def get_all_schema_names(database_name: str) -> List[str]:
    """
    Get list of all schema names for a database.
    
    Args:
        database_name (str): Name of the database
        
    Returns:
        List[str]: List of schema names
    """
    try:
        connector = SQLConnector(database=database_name)
        query = "SELECT name FROM sys.schemas ORDER BY name;"
        _, results = connector.execute_query(query)
        connector.close()
        return [row['name'] for row in results] if results else []
    except Exception as e:
        logger.error(f"Error getting schema names: {str(e)}")
        return []

def get_schema_map(database_name: str = None) -> Dict:
    """
    Get detailed schema information for the specified database.
    This is the main function to get schema information, with caching.
    
    Args:
        database_name (str, optional): Name of the database to get schema for
        
    Returns:
        Dict: Schema information including tables, columns, PKs, and FKs
    """
    return get_schema_map_from_cache(database_name)

def get_schema_map_formatted(database_name: str = None) -> str:
    """
    Get schema information as a formatted string for display/logging.
    
    Args:
        database_name (str, optional): Name of the database
        
    Returns:
        str: Formatted schema information
    """
    schema_map = get_schema_map(database_name)
    
    # Format schema information
    formatted_schema = []
    for schema_name, schema_info in schema_map.items():
        formatted_schema.append(f"\n{schema_name} Schema:")
        for table_name, table_info in schema_info['tables'].items():
            formatted_schema.append(f"  {table_name} Table:")
            for column_name, column_info in table_info['columns'].items():
                formatted_schema.append(
                    f"    - {column_name} ({column_info['type']})"
                    f"{' [PK]' if column_name in table_info['primary_keys'] else ''}"
                )

            # Add FK information
            for fk in table_info['foreign_keys']:
                formatted_schema.append(
                    f"    - FK: {fk['column']} -> {fk['references']}"
                )
    
    return "\n".join(formatted_schema)

def clean_pretty_sql(raw_sql: str) -> str:
    """
    Prettify and format SQL output for Clean Code SQL practices.
    """
    formatted = sqlparse.format(
        raw_sql,
        reindent=True,
        keyword_case="upper",
        strip_comments=True
    )
    return formatted

def format_sql_query(sql: str) -> str:
    """
    Format a SQL query to make it easier to read using sqlparse.

    Args:
        sql (str): Raw SQL query.

    Returns:
        str: Formatted SQL query.
    """
    try:
        formatted = sqlparse.format(
            sql,
            reindent=True,
            keyword_case='upper',
            indent_width=4,
            strip_comments=True
        )
        return formatted
    except Exception as e:
        logger.warning(f"[SQLFormatter] Failed to format SQL: {e}")
        return sql  # Return unformatted SQL as fallback

def build_visual_query():
    """Visual query builder interface"""
    try:
        # Create connector without parameters
        connector = SQLConnector()
        
        # Get schema information
        schema_map = get_schema_map_from_cache()
        
        if not schema_map:
            return None, "Could not load schema information"
            
        # Let user select schema and table
        schemas = list(schema_map.keys())
        selected_schema = st.selectbox("Select Schema", schemas)
        
        if selected_schema:
            tables = list(schema_map[selected_schema]['tables'].keys())
            selected_table = st.selectbox("Select Table", tables)
            
            if selected_table:
                # Get columns for the selected table
                columns = schema_map[selected_schema]['tables'][selected_table]['columns']
                column_names = list(columns.keys())
                
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
                    
                    return sql, None
        
        connector.close()
        return None, None
        
    except Exception as e:
        return None, f"Error in query builder: {str(e)}"

@lru_cache(maxsize=128)
def get_table_description(table_name: str, schema_name: str = 'dbo') -> Optional[Dict]:
    """
    Get cached table description. Returns None if table doesn't exist.
    Uses lru_cache for caching results.
    """
    try:
        connector = SQLConnector()
        description = describe_table(table_name, schema_name, connector)
        connector.close()
        return description
    except Exception as e:
        logger.error(f"Error getting table description: {str(e)}")
        return None

def clear_table_cache():
    """Clear the table description cache"""
    get_table_description.cache_clear()

def get_schema_map_with_descriptions() -> Dict:
    """
    Get schema map with detailed table descriptions.
    Uses cached table descriptions where available.
    """
    try:
        # Get base schema map from cache
        schema_map = get_schema_map_from_cache()
        if not schema_map:
            logger.error("Failed to get schema map from cache")
            return {}
        
        enhanced_schema = {}
        successful_tables = 0
        
        for schema_name, schema_info in schema_map.items():
            enhanced_schema[schema_name] = {'tables': {}}
            for table_name in schema_info.get('tables', {}):
                # Get cached description or fetch new one
                description = get_table_description(table_name, schema_name)
                if description and description.get('columns'):
                    enhanced_schema[schema_name]['tables'][table_name] = description
                    successful_tables += 1
        
        if successful_tables == 0:
            logger.error("No table descriptions were successfully retrieved")
            return {}
            
        logger.info(f"Successfully retrieved descriptions for {successful_tables} tables")
        return enhanced_schema
        
    except Exception as e:
        logger.error(f"Error getting schema map with descriptions: {str(e)}")
        return {}

def validate_query(query: str, schema_map: dict) -> dict:
    """Validate SQL query against schema and T-SQL dialect"""
    try:
        # Basic T-SQL syntax validation
        if "LIMIT" in query.upper():
            return {
                "is_valid": False,
                "error": "LIMIT is not supported in T-SQL. Use TOP instead."
            }
            
        # Check for basic SQL syntax
        required_keywords = ["SELECT", "FROM"]
        for keyword in required_keywords:
            if keyword not in query.upper():
                return {
                    "is_valid": False,
                    "error": f"Missing required keyword: {keyword}"
                }
        
        # Check table names against schema
        table_pattern = r'FROM\s+([^\s,;]+)|JOIN\s+([^\s,;]+)'
        table_matches = re.finditer(table_pattern, query, re.IGNORECASE)
        
        for match in table_matches:
            table = match.group(1) or match.group(2)  # Get the matched table name
            # Check if table exists in schema_map
            if '.' not in table:
                return {
                    "is_valid": False,
                    "error": f"Table '{table}' must use a fully qualified name (schema.table)"
                }
            schema_name, table_name = table.split('.', 1)
            if schema_name not in schema_map or table_name not in schema_map[schema_name]:
                return {
                    "is_valid": False,
                    "error": f"Table {table} not found in schema"
                }
        
        # If all checks pass
        return {
            "is_valid": True,
            "error": None
        }
        
    except Exception as e:
        logger.error(f"Error in validate_query: {str(e)}")
        return {
            "is_valid": False,
            "error": str(e)
        }

def validate_query_dialect(query: str, schema_map: dict) -> dict:
    """Validate SQL query dialect and convert to T-SQL if needed"""
    try:
        # Convert LIMIT to TOP
        if "LIMIT" in query.upper():
            # Extract the LIMIT number
            limit_match = re.search(r'LIMIT\s+(\d+)', query, re.IGNORECASE)
            if limit_match:
                limit_num = limit_match.group(1)
                # Remove the LIMIT clause
                query = re.sub(r'LIMIT\s+\d+', '', query, flags=re.IGNORECASE)
                # Add TOP clause after SELECT
                query = re.sub(r'SELECT\s+', f'SELECT TOP {limit_num} ', query, flags=re.IGNORECASE)
        
        # Validate the query
        validation_result = validate_query(query, schema_map)
        return {
            "is_valid": validation_result["is_valid"],
            "error": validation_result.get("error", ""),
            "query": query
        }
        
    except Exception as e:
        logger.error(f"Error in validate_query_dialect: {str(e)}")
        return {
            "is_valid": False,
            "error": str(e),
            "query": query
        }

def _convert_type_to_sqlglot(sql_type: str) -> str:
    """
    Convert SQL Server types to SQLGlot compatible types.
    
    Args:
        sql_type (str): SQL Server type
        
    Returns:
        str: SQLGlot compatible type
    """
    type_mapping = {
        'int': 'INT',
        'bigint': 'BIGINT',
        'smallint': 'SMALLINT',
        'tinyint': 'TINYINT',
        'bit': 'BOOLEAN',
        'decimal': 'DECIMAL',
        'numeric': 'DECIMAL',
        'money': 'DECIMAL',
        'smallmoney': 'DECIMAL',
        'float': 'DOUBLE',
        'real': 'FLOAT',
        'datetime': 'TIMESTAMP',
        'datetime2': 'TIMESTAMP',
        'smalldatetime': 'TIMESTAMP',
        'date': 'DATE',
        'time': 'TIME',
        'char': 'CHAR',
        'varchar': 'VARCHAR',
        'text': 'TEXT',
        'nchar': 'CHAR',
        'nvarchar': 'VARCHAR',
        'ntext': 'TEXT',
        'binary': 'BINARY',
        'varbinary': 'VARBINARY',
        'image': 'VARBINARY',
        'xml': 'VARCHAR',
        'uniqueidentifier': 'UUID'
    }
    
    # Extract base type and remove length/precision
    base_type = sql_type.split('(')[0].lower().strip()
    return type_mapping.get(base_type, 'VARCHAR')  # Default to VARCHAR if type not found 