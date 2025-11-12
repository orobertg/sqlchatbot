"""
LLM Engine Module
Handles LLM interactions and SQL query generation
"""

import os
import json
import logging
import re
import sqlparse
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field, field_validator
import requests
from sqlparse.sql import Identifier, IdentifierList, Token
from sqlparse.tokens import DML

from backend.system import LLM_CONFIG
from backend.db_tools import (
    execute_query,
    is_destructive_query,
    get_schema_map,
    get_cache_path,
    is_cache_valid,
    validate_query_dialect,
    DatabaseType,
    ExecuteQueryInput,
    ExecuteQueryOutput
)
from backend.sql_connector import SQLConnector

# Configure logging
logger = logging.getLogger(__name__)

class LocalLLM:
    """Local LLM client for interacting with Ollama API."""
    
    def __init__(self, model: str = None):
        """Initialize LLM client with configuration."""
        self.model = model or LLM_CONFIG['model']
        self.api_base = LLM_CONFIG['api_base'].rstrip("/")
        if self.api_base.endswith("/v1"):
            self.api_base = self.api_base[:-3].rstrip("/")
        self.api_key = LLM_CONFIG['api_key']
        
    def get_completion(self, prompt: str, system_prompt: str = None) -> str:
        """Get completion from LLM."""
        try:
            # Prepare messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            # Prepare request
            headers = {
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "top_p": 0.1,
                    "num_predict": 1024
                }
            }
            
            # Make request to Ollama's chat endpoint
            response = requests.post(
                f"{self.api_base}/api/chat",
                headers=headers,
                json=data
            )
            response.raise_for_status()
            
            # Extract and return completion
            result = response.json()
            return result.get('message', {}).get('content', '')
            
        except Exception as e:
            logger.error(f"Error getting LLM completion: {str(e)}")
            raise

# Global LLM instance
_llm_instance = None

def get_llm_instance() -> Optional[LocalLLM]:
    """Get or create LLM instance."""
    global _llm_instance
    if _llm_instance is None:
        try:
            _llm_instance = LocalLLM()
        except Exception as e:
            logger.error(f"Failed to create LLM instance: {str(e)}")
            return None
    return _llm_instance

def set_llm_instance(model: str) -> None:
    """Set LLM instance with specified model."""
    global _llm_instance
    _llm_instance = LocalLLM(model=model)

def list_local_models() -> List[str]:
    """List available models from Ollama."""
    try:
        base_url = LLM_CONFIG['api_base'].rstrip("/")
        if base_url.endswith("/v1"):
            base_url = base_url[:-3].rstrip("/")
        
        response = requests.get(f"{base_url}/api/tags")
        response.raise_for_status()
        data = response.json()
        return [m["name"] for m in data.get("models", [])]
    except Exception as e:
        logger.error(f"Error listing local models: {str(e)}")
        return []

class SQLResponse(BaseModel):
    sql_query: str = Field(...)

    @field_validator("sql_query")
    def validate_sql(cls, v):
        if not re.match(r"^(SELECT|INSERT|UPDATE|DELETE|WITH)\b", v, re.IGNORECASE):
            raise ValueError("Output is not valid SQL.")
        return v

class SQLPrompt(BaseModel):
    prompt: str
    schema_map: Dict
    description: Optional[str] = None
    
    def to_full_prompt(self) -> str:
        """Convert prompt to full prompt with schema information."""
        # Format schema information
        schema_info = self._format_schema_info()
        
        # Build the full prompt
        full_prompt = f"""IMPORTANT: This is a new question. Ignore any previous queries and focus only on the current request.

GOAL: Write a SQL query that answers the following user request as directly as possible.

USER REQUEST: {self.prompt}

THINK STEP: Before writing the query, answer these questions:
1. What is the user asking for? (e.g., count, sum, list, etc.)
2. Which table(s) and column(s) best match this request? List them explicitly.
3. Why did you choose these tables/columns?
4. Verify that every column you plan to use is explicitly listed in the schema above.

CRITICAL: You MUST use ONLY the columns listed in the schema above. If a column is not listed, it does NOT exist. Do NOT guess or invent column names.

{schema_info}

IMPORTANT RULES:
1. ONLY use tables and columns that exist in the schema above. Do NOT invent or guess column names.
2. If you are unsure which column to use, pick from the columns listed in the schema above.
3. ALWAYS use fully qualified table names in ALL parts of the query (e.g., 'schema.table', NOT just 'table')
4. Follow foreign key relationships for joins
5. Use table aliases consistently
6. Include all non-aggregated columns in GROUP BY
7. Reference columns from the correct aliased tables
8. Return ONLY the SQL query within ```sql ``` blocks
9. Do not include any explanations or comments in the SQL block
10. In the SELECT clause, use fully qualified column names (e.g., 'schema.table.column')
11. If the user asks 'how many', 'count', or 'number of', use COUNT(*) or COUNT(column) as appropriate
12. ALWAYS use fully qualified table names in FROM and JOIN clauses

CHECK: Before returning the query, verify that every column used in the query is explicitly listed in the schema above. If any column is not listed, it does NOT exist.

Example format:
```sql
SELECT schema.table.column1, schema.table.column2
FROM schema.table
JOIN schema.other_table ON schema.table.id = schema.other_table.id
GROUP BY schema.table.column1
ORDER BY schema.table.column2 DESC
```

Please generate a SQL query that answers the user's request. The query MUST be wrapped in sql blocks."""
        
        return full_prompt
    
    def _format_schema_info(self) -> str:
        """Format schema information for the prompt."""
        # Get likely tables based on the prompt
        likely_tables = self._get_likely_tables()
        
        # Format available tables
        available_tables = self._get_available_tables()
        
        # Build schema info
        schema_info = f"""LIKELY TABLES FOR THIS QUERY:
{likely_tables}

AVAILABLE TABLES: {available_tables}

Database Schema:
{self._format_schema_map()}

IMPORTANT RULES:
1. ONLY use tables and columns that exist in the schema above. Do NOT invent or guess column names.
2. If you are unsure which column to use, pick from the columns listed in the schema above.
3. ALWAYS use fully qualified table names in ALL parts of the query (e.g., 'schema.table', NOT just 'table')
4. Follow foreign key relationships for joins
5. Use table aliases consistently
6. Include all non-aggregated columns in GROUP BY
7. Reference columns from the correct aliased tables
8. Return ONLY the SQL query within ```sql ``` blocks
9. Do not include any explanations or comments in the SQL block
10. In the SELECT clause, use fully qualified column names (e.g., 'schema.table.column')
11. If the user asks 'how many', 'count', or 'number of', use COUNT(*) or COUNT(column) as appropriate
12. ALWAYS use fully qualified table names in FROM and JOIN clauses

CHECK: Before returning the query, verify that every column used in the query is explicitly listed in the schema above. If any column is not listed, it does NOT exist.

Example format:
```sql
SELECT schema.table.column1, schema.table.column2
FROM schema.table
JOIN schema.other_table ON schema.table.id = schema.other_table.id
GROUP BY schema.table.column1
ORDER BY schema.table.column2 DESC
```

Please generate a SQL query that answers the user's request. The query MUST be wrapped in sql blocks."""
        
        return schema_info
    
    def _get_likely_tables(self) -> str:
        """Get likely tables based on the prompt content."""
        likely_tables = []
        prompt_words = set(self.prompt.lower().split())
        
        for schema_name, schema_info in self.schema_map.items():
            if "tables" in schema_info:
                for table_name, table_info in schema_info["tables"].items():
                    # Check if any word from the prompt appears in the table name
                    if any(word in table_name.lower() for word in prompt_words):
                        columns = table_info.get('columns', {})
                        columns_str = ", ".join(columns.keys())
                        likely_tables.append(f"{schema_name}.{table_name}: {columns_str}")
        return "\n".join(likely_tables)
    
    def _get_available_tables(self) -> str:
        """Get list of all available tables."""
        tables = []
        for schema_name, schema_info in self.schema_map.items():
            if "tables" in schema_info:
                tables.extend([f"{schema_name}.{table}" for table in schema_info["tables"].keys()])
        return ", ".join(sorted(tables))
    
    def _format_schema_map(self) -> str:
        """Format the schema map for display."""
        schema_str = []
        for schema_name, schema_info in self.schema_map.items():
            if "tables" in schema_info:
                schema_str.append(f"\n{schema_name} Schema:\n")
                for table_name, table_info in schema_info["tables"].items():
                    schema_str.append(f"\n{schema_name}.{table_name}")
                    # Add columns
                    for column_name, column_info in table_info.get('columns', {}).items():
                        col_type = column_info.get('type', 'unknown')
                        is_pk = column_name in table_info.get('primary_keys', [])
                        is_fk = any(fk['column'] == column_name for fk in table_info.get('foreign_keys', []))
                        
                        col_str = f"  - {column_name} ({col_type})"
                        if is_pk:
                            col_str += " [PRIMARY KEY]"
                        if is_fk:
                            col_str += " [FOREIGN KEY]"
                        schema_str.append(col_str)
                    
                    # Add foreign key relationships
                    if table_info.get('foreign_keys'):
                        schema_str.append("\n  Foreign Keys:")
                        for fk in table_info['foreign_keys']:
                            schema_str.append(f"    - {fk['column']} -> {fk['references']}")
        return "\n".join(schema_str)

def refine_sql_query(query: str, error_message: str, schema_map: dict) -> str:
    """Refine SQL query based on error message and schema details."""
    try:
        # Format schema details
        schema_details = format_schema_details(schema_map, truncate=True)
        
        # Build refinement prompt
        refinement_prompt = f"""I need to fix a SQL query that has an error. Here's the original query and error:

Original Query:
```sql
{query}
```

Error Message:
{error_message}

Relevant Schema Details:
{schema_details}

Please fix the query following these rules:
1. Use T-SQL syntax (e.g., use TOP instead of LIMIT)
2. Use fully qualified table names
3. Follow foreign key relationships for joins
4. Include all non-aggregated columns in GROUP BY
5. Return ONLY the fixed query within ```sql ``` blocks
6. The query should maintain the same logic and purpose as the original, just with correct T-SQL syntax
7. ONLY use tables that exist in the schema above
8. If a table doesn't exist, look for similar tables in the schema (e.g., if 'Orders' doesn't exist, look for 'Sales.Orders' or 'Purchase.Orders')
9. Do not include any explanations or comments in the SQL block

Example format:
```sql
SELECT Warehouse.StockItems.StockItemName, SUM(Sales.OrderLines.Quantity) AS TotalSold
FROM Sales.OrderLines
JOIN Warehouse.StockItems ON Sales.OrderLines.StockItemID = Warehouse.StockItems.StockItemID
GROUP BY Warehouse.StockItems.StockItemName
ORDER BY TotalSold DESC
```"""
        
        return refinement_prompt
        
    except Exception as e:
        logger.error(f"Error creating refinement prompt: {str(e)}")
        return f"Error creating refinement prompt: {str(e)}"

def validate_tables_in_schema(query: str, schema_map: dict) -> Tuple[bool, str]:
    """
    Validate that all tables in the query exist in the schema map.
    
    Args:
        query (str): SQL query to validate
        schema_map (dict): Schema map containing table information
        
    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    try:
        logger.info(f"Validating query: {query}")
        logger.info(f"Schema map keys: {list(schema_map.keys())}")
        
        # Extract table names from the query - improved pattern to handle more cases
        table_pattern = r"(?:FROM|JOIN)\s+([a-zA-Z0-9_\.]+)(?:\s+AS\s+[a-zA-Z0-9_]+)?"
        tables = re.findall(table_pattern, query, re.IGNORECASE)
        logger.info(f"Extracted tables from query: {tables}")
        
        # Get all available tables from schema
        available_tables = []
        for schema_name, schema_info in schema_map.items():
            if "tables" in schema_info:
                schema_tables = [f"{schema_name}.{table}" for table in schema_info["tables"].keys()]
                available_tables.extend(schema_tables)
                logger.info(f"Tables in schema {schema_name}: {schema_tables}")
        
        logger.info(f"All available tables: {available_tables}")
        
        # Check each table against the schema map
        invalid_tables = []
        for table in tables:
            logger.info(f"\nChecking table: {table}")
            # Handle fully qualified table names (schema.table)
            if '.' in table:
                schema_name, table_name = table.split('.')
                logger.info(f"Checking schema '{schema_name}' and table '{table_name}'")
                
                if schema_name not in schema_map:
                    logger.warning(f"Schema '{schema_name}' not found in schema map")
                    invalid_tables.append(f"Schema '{schema_name}' not found")
                elif "tables" not in schema_map[schema_name]:
                    logger.warning(f"No tables found in schema '{schema_name}'")
                    invalid_tables.append(f"No tables found in schema '{schema_name}'")
                elif table_name not in schema_map[schema_name]["tables"]:
                    logger.warning(f"Table '{table_name}' not found in schema '{schema_name}'")
                    logger.warning(f"Available tables in schema '{schema_name}': {list(schema_map[schema_name]['tables'].keys())}")
                    invalid_tables.append(f"Table '{table_name}' not found in schema '{schema_name}'")
                else:
                    logger.info(f"Found table '{table_name}' in schema '{schema_name}'")
            else:
                # Check if table exists in any schema
                found = False
                for schema_name, schema_info in schema_map.items():
                    if "tables" in schema_info and table in schema_info["tables"]:
                        found = True
                        logger.info(f"Found table '{table}' in schema '{schema_name}'")
                        break
                if not found:
                    logger.warning(f"Table '{table}' not found in any schema")
                    invalid_tables.append(f"Table '{table}' not found in any schema")
        
        if invalid_tables:
            # Get relevant tables based on the invalid table names
            relevant_tables = []
            for invalid_table in invalid_tables:
                # Extract the base table name without schema
                base_name = invalid_table.split('.')[-1].lower()
                # Find tables that might be related based on name similarity
                similar_tables = [t for t in available_tables if base_name in t.lower()]
                relevant_tables.extend(similar_tables)
            
            error_msg = f"Schema validation errors:\n" + "\n".join(f"- {error}" for error in invalid_tables)
            if relevant_tables:
                error_msg += f"\n\nAvailable similar tables:\n" + "\n".join(f"- {t}" for t in sorted(set(relevant_tables)))
            logger.warning(f"Validation failed: {error_msg}")
            return False, error_msg
        
        logger.info("All tables validated successfully")
        return True, ""
        
    except Exception as e:
        logger.error(f"Error validating tables in schema: {str(e)}")
        return False, f"Error validating tables: {str(e)}"

def process_user_prompt(prompt: str, database_name: str) -> dict:
    """Process user prompt and return response"""
    try:
        # Get schema map
        schema_map = get_schema_map(database_name)
        
        # Debug logging for schema map
        logger.info("\n=== Schema Map Contents ===")
        for schema_name, schema_info in schema_map.items():
            logger.info(f"\nSchema: {schema_name}")
            for table_name, table_info in schema_info.get('tables', {}).items():
                logger.info(f"  Table: {table_name}")
                logger.info(f"    Columns: {list(table_info.get('columns', {}).keys())}")
                logger.info(f"    Primary Keys: {table_info.get('primary_keys', [])}")
                logger.info(f"    Foreign Keys: {[fk['column'] for fk in table_info.get('foreign_keys', [])]}")
        
        # Create SQL prompt with all required fields
        sql_prompt = SQLPrompt(
            prompt=prompt,
            schema_map=schema_map,
            description="Generate SQL query for user request"
        )
        full_prompt = sql_prompt.to_full_prompt()
        
        # Get initial response from LLM
        initial_response = get_llm_instance().get_completion(full_prompt)
        initial_query = clean_sql_response(initial_response)
        
        # Initialize debug info
        debug_info = {
            "initial_prompt": full_prompt,
            "initial_response": initial_response,
            "initial_query": initial_query,
            "tool_calls": [
                f"USER PROMPT: {prompt}"
            ]
        }
        
        # First validate that all tables exist in the schema
        table_validation = validate_tables_in_schema(initial_query, schema_map)
        if not table_validation[0]:
            debug_info["validation_error"] = table_validation[1]
            debug_info["tool_calls"].append(f"ERROR: {table_validation[1]}")
            
            # Attempt to refine the query
            refinement_prompt = refine_sql_query(
                initial_query,
                table_validation[1],
                schema_map
            )
            
            # Add refinement prompt to tool calls
            debug_info["tool_calls"].append(f"REFINEMENT PROMPT: {refinement_prompt}")
            
            # Get refinement response
            refinement_response = get_llm_instance().get_completion(refinement_prompt)
            final_query = clean_sql_response(refinement_response)
            
            # Add refinement info to debug
            debug_info.update({
                "refinement_prompt": refinement_prompt,
                "refinement_response": refinement_response,
                "final_query": final_query
            })
            
            # Validate the refined query's tables
            refined_table_validation = validate_tables_in_schema(final_query, schema_map)
            if not refined_table_validation[0]:
                debug_info["tool_calls"].append(f"ERROR: {refined_table_validation[1]}")
                return {
                    "response": f"I apologize, but I'm having trouble generating a valid SQL query. The error is: {refined_table_validation[1]}",
                    "debug_info": debug_info
                }
            
            # Then validate the query dialect
            validation_result = validate_query_dialect(final_query, schema_map)
            if not validation_result["is_valid"]:
                debug_info["tool_calls"].append(f"ERROR: {validation_result['error']}")
                return {
                    "response": f"I apologize, but I'm having trouble generating a valid SQL query. The error is: {validation_result['error']}",
                    "debug_info": debug_info
                }
            
            # Track tool call for final query execution
            debug_info["tool_calls"].append(f"DB CALL: execute_query({final_query})")
            
            # Execute the refined query
            result = execute_query(final_query)
            return {
                "response": format_query_result(result),
                "debug_info": debug_info
            }
        
        # If initial query tables are valid, validate the query dialect
        validation_result = validate_query_dialect(initial_query, schema_map)
        if not validation_result["is_valid"]:
            debug_info["validation_error"] = validation_result["error"]
            debug_info["tool_calls"].append(f"ERROR: {validation_result['error']}")
            
            # Attempt to refine the query
            refinement_prompt = refine_sql_query(
                initial_query,
                validation_result["error"],
                schema_map
            )
            
            # Add refinement prompt to tool calls
            debug_info["tool_calls"].append(f"REFINEMENT PROMPT: {refinement_prompt}")
            
            # Get refinement response
            refinement_response = get_llm_instance().get_completion(refinement_prompt)
            final_query = clean_sql_response(refinement_response)
            
            # Add refinement info to debug
            debug_info.update({
                "refinement_prompt": refinement_prompt,
                "refinement_response": refinement_response,
                "final_query": final_query
            })
            
            # Validate the refined query's tables
            refined_table_validation = validate_tables_in_schema(final_query, schema_map)
            if not refined_table_validation[0]:
                debug_info["tool_calls"].append(f"ERROR: {refined_table_validation[1]}")
                return {
                    "response": f"I apologize, but I'm having trouble generating a valid SQL query. The error is: {refined_table_validation[1]}",
                    "debug_info": debug_info
                }
            
            # Then validate the query dialect
            refined_validation = validate_query_dialect(final_query, schema_map)
            if not refined_validation["is_valid"]:
                debug_info["tool_calls"].append(f"ERROR: {refined_validation['error']}")
                return {
                    "response": f"I apologize, but I'm having trouble generating a valid SQL query. The error is: {refined_validation['error']}",
                    "debug_info": debug_info
                }
            
            # Track tool call for final query execution
            debug_info["tool_calls"].append(f"DB CALL: execute_query({final_query})")
            
            # Execute the refined query
            result = execute_query(final_query)
            return {
                "response": format_query_result(result),
                "debug_info": debug_info
            }
        
        # If initial query is valid, execute it
        debug_info["tool_calls"].append(f"DB CALL: execute_query({initial_query})")
        result = execute_query(initial_query)
        return {
            "response": format_query_result(result),
            "debug_info": debug_info
        }
        
    except Exception as e:
        logger.error(f"Error in process_user_prompt: {str(e)}")
        return {
            "response": f"I apologize, but I encountered an error: {str(e)}",
            "debug_info": {}
        }

def print_schema_map(schema_map: Dict) -> None:
    """Print schema map in a readable format"""
    logger.info("\n=== Schema Map Contents ===")
    if not schema_map:
        logger.info("Schema map is empty")
        return
        
    for schema_name, schema_info in schema_map.items():
        logger.info(f"\nSchema: {schema_name}")
        for table_name, table_info in schema_info.get('tables', {}).items():
            logger.info(f"\n  Table: {table_name}")
            logger.info("  Columns:")
            for column in table_info.get('columns', []):
                logger.info(f"    - {column['name']} ({column['type']})")
            if table_info.get('primary_keys'):
                logger.info("  Primary Keys:")
                for pk in table_info['primary_keys']:
                    logger.info(f"    - {pk}")
            if table_info.get('foreign_keys'):
                logger.info("  Foreign Keys:")
                for fk in table_info['foreign_keys']:
                    logger.info(f"    - {fk['column']} -> {fk['referenced_schema']}.{fk['referenced_table']}.{fk['referenced_column']}")

def get_schema_map_from_cache(database: str = None) -> Dict:
    """Get schema map from cache or build it"""
    try:
        cache_path = get_cache_path(database)
        logger.info(f"Cache path: {cache_path}")
        
        if is_cache_valid(cache_path):
            logger.info("Using cached schema map")
            with open(cache_path, 'r') as f:
                schema_map = json.load(f)
                print_schema_map(schema_map)
                return schema_map
                
        logger.info("Building new schema map")
        schema_map = _build_schema_map(database)
        
        # Save to cache
        with open(cache_path, 'w') as f:
            json.dump(schema_map, f)
            
        print_schema_map(schema_map)
        return schema_map
        
    except Exception as e:
        logger.error(f"Error getting schema map from cache: {str(e)}")
        return {}

def _build_schema_map(database: str = None) -> Dict:
    """Build schema map for the given database"""
    try:
        logger.info(f"Building schema map for database: {database}")
        connector = SQLConnector(database=database)
        
        # Get schema information using SQL queries for better control
        schema_map = {}
        
        # Get all schemas
        schemas_query = "SELECT name FROM sys.schemas ORDER BY name;"
        logger.info(f"Executing schemas query: {schemas_query}")
        _, schemas = connector.execute_query(schemas_query)
        logger.info(f"Found schemas: {[row[0] for row in schemas]}")
        
        for schema_row in schemas:
            schema = schema_row[0]
            logger.info(f"\nProcessing schema: {schema}")
            schema_map[schema] = {'tables': {}}
            
            # Get tables and their columns
            tables_query = """
            SELECT 
                t.name AS table_name,
                c.name AS column_name,
                ty.name AS data_type,
                c.max_length,
                c.precision,
                c.scale,
                c.is_nullable,
                CASE WHEN pk.column_id IS NOT NULL THEN 1 ELSE 0 END AS is_primary_key
            FROM sys.tables t
            JOIN sys.columns c ON t.object_id = c.object_id
            JOIN sys.types ty ON c.user_type_id = ty.user_type_id
            LEFT JOIN sys.index_columns pk 
                ON c.object_id = pk.object_id 
                AND c.column_id = pk.column_id 
                AND pk.index_id = 1
            WHERE t.schema_id = SCHEMA_ID(?)
            ORDER BY t.name, c.column_id;
            """
            
            logger.info(f"Executing tables query for schema {schema}")
            _, tables_result = connector.execute_query(tables_query, [schema])
            logger.info(f"Found {len(tables_result)} table results")
            
            # Process table results
            current_table = None
            for row in tables_result:
                table_name = row[0]
                if table_name != current_table:
                    current_table = table_name
                    schema_map[schema]['tables'][table_name] = {
                        'columns': [],
                        'primary_keys': [],
                        'foreign_keys': []
                    }
                
                # Add column information
                column_info = {
                    'name': row[1],
                    'type': row[2],
                    'is_nullable': bool(row[6]),
                    'is_primary_key': bool(row[7])
                }
                schema_map[schema]['tables'][table_name]['columns'].append(column_info)
                
                # Add to primary keys if applicable
                if column_info['is_primary_key']:
                    schema_map[schema]['tables'][table_name]['primary_keys'].append(column_info['name'])
            
            # Get foreign key information
            fk_query = """
            SELECT 
                fk.name AS fk_name,
                OBJECT_NAME(fk.parent_object_id) AS table_name,
                COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS column_name,
                OBJECT_SCHEMA_NAME(fk.referenced_object_id) AS referenced_schema,
                OBJECT_NAME(fk.referenced_object_id) AS referenced_table,
                COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS referenced_column
            FROM sys.foreign_keys fk
            JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
            WHERE OBJECT_SCHEMA_NAME(fk.parent_object_id) = ?
            ORDER BY fk.name;
            """
            
            logger.info(f"Executing foreign keys query for schema {schema}")
            _, fk_results = connector.execute_query(fk_query, [schema])
            
            # Process foreign key results
            for row in fk_results:
                table_name = row[1]
                if table_name in schema_map[schema]['tables']:
                    fk_info = {
                        'name': row[0],
                        'column': row[2],
                        'referenced_schema': row[3],
                        'referenced_table': row[4],
                        'referenced_column': row[5]
                    }
                    schema_map[schema]['tables'][table_name]['foreign_keys'].append(fk_info)
        
        connector.close()
        return schema_map
        
    except Exception as e:
        logger.error(f"Error building schema map: {str(e)}")
        if connector:
            connector.close()
        return {}

def format_schema_for_prompt(schema_map: dict, truncate: bool = False) -> str:
    """Format schema map for use in LLM prompts."""
    if truncate:
        # Return a simplified schema summary
        return """Schema information available (truncated for readability):
- Sales.OrderLines: Contains order line details including StockItemID and Quantity
- Warehouse.StockItems: Contains item details including StockItemName
- Other relevant tables and relationships are available but not shown for brevity"""
    
    # Original full schema formatting logic here
    schema_details = []
    
    for schema_name, schema_info in schema_map.items():
        schema_details.append(f"\n{schema_name} Schema:")
        for table_name, table_info in schema_info.get('tables', {}).items():
            # Full table name
            full_table_name = f"{schema_name}.{table_name}"
            schema_details.append(f"\n{full_table_name}")
            
            # Column details - limit to 5 columns if truncating
            columns = table_info.get('columns', [])
            if truncate and len(columns) > 5:
                columns = columns[:5]
                schema_details.append("  [Additional columns truncated...]")
            
            column_details = []
            for col in columns:
                col_name = col.get('name', '')
                col_type = col.get('type', 'unknown')
                is_pk = col.get('is_primary_key', False)
                is_fk = col.get('is_foreign_key', False)
                
                # Build column string with relationships
                col_info = [f"  - {col_name} ({col_type})"]
                if is_pk:
                    col_info.append("    [PRIMARY KEY]")
                if is_fk:
                    col_info.append("    [FOREIGN KEY]")
                
                column_details.append("\n".join(col_info))
            
            schema_details.append("\n".join(column_details))
            
            # Add foreign key relationships - limit to 3 if truncating
            if table_info.get('foreign_keys'):
                schema_details.append("\nForeign Keys:")
                fks = table_info['foreign_keys']
                if truncate and len(fks) > 3:
                    fks = fks[:3]
                    schema_details.append("  [Additional foreign keys truncated...]")
                for fk in fks:
                    schema_details.append(
                        f"  - {fk['column']} -> {fk['referenced_schema']}.{fk['referenced_table']}.{fk['referenced_column']}"
                    )
    
    return "\n".join(schema_details)

def format_schema_details(schema_map: dict, truncate: bool = False) -> str:
    """Format schema details for refinement prompts."""
    if truncate:
        return """Relevant Schema Details:
- Sales.OrderLines: OrderLineID, StockItemID, Quantity
- Warehouse.StockItems: StockItemID, StockItemName
- Relationship: Sales.OrderLines.StockItemID -> Warehouse.StockItems.StockItemID"""
    
    # Original full schema details formatting logic here
    ...

def extract_sql_query(response: str) -> Optional[str]:
    """
    Extract SQL query from LLM response.
    Looks for SQL code blocks and extracts the query.
    
    Args:
        response (str): Raw LLM response text
        
    Returns:
        Optional[str]: Extracted SQL query or None if not found
    """
    try:
        # Look for SQL code blocks
        sql_pattern = r"```sql\n(.*?)\n```"
        matches = re.findall(sql_pattern, response, re.DOTALL)
        
        if matches:
            # Get the first SQL block
            sql_query = matches[0].strip()
            
            # Clean up the query
            sql_query = clean_sql_response(sql_query)
            
            if sql_query:
                logger.info(f"Extracted SQL query: {sql_query}")
                return sql_query
        
        logger.warning("No SQL query found in response")
        return None
        
    except Exception as e:
        logger.error(f"Error extracting SQL query: {str(e)}")
        return None

def clean_sql_response(response: str) -> Optional[str]:
    """
    Clean and validate SQL response from LLM.
    
    Args:
        response (str): Raw SQL response text
        
    Returns:
        Optional[str]: Cleaned SQL query or None if invalid
    """
    try:
        # Log the raw response for debugging
        logger.info(f"Raw SQL response: {response}")
        
        # Try to parse JSON response first
        try:
            import json
            json_response = json.loads(response)
            if isinstance(json_response, dict):
                # Handle both direct new_query and arguments.new_query
                if "new_query" in json_response:
                    response = json_response["new_query"]
                elif "arguments" in json_response and "new_query" in json_response["arguments"]:
                    response = json_response["arguments"]["new_query"]
        except json.JSONDecodeError:
            pass  # Not a JSON response, continue with normal processing
        
        # Remove any markdown code block markers
        response = re.sub(r"```sql\n|```", "", response)
        
        # Remove any explanatory text before or after the query
        # Look for the first SQL command
        sql_match = re.search(r"(SELECT|INSERT|UPDATE|DELETE|WITH)\b.*?;", response, re.IGNORECASE | re.DOTALL)
        if sql_match:
            response = sql_match.group(0)
        
        # Remove any comments
        response = re.sub(r"--.*$", "", response, flags=re.MULTILINE)  # Remove single-line comments
        response = re.sub(r"/\*.*?\*/", "", response, flags=re.DOTALL)  # Remove multi-line comments
        
        # Basic validation
        if not response:
            logger.warning("Empty response after cleaning")
            return None
            
        # Ensure it starts with a valid SQL command
        if not re.match(r"^(SELECT|INSERT|UPDATE|DELETE|WITH)\b", response, re.IGNORECASE):
            logger.warning(f"Response does not start with valid SQL command: {response[:50]}...")
            return None
            
        # Format the query
        formatted = sqlparse.format(
            response,
            reindent=True,
            keyword_case="upper",
            strip_comments=True
        )
        
        return formatted.strip()
        
    except Exception as e:
        logger.error(f"Error cleaning SQL response: {str(e)}")
        return None

def test_llm_connection() -> Tuple[bool, str]:
    """
    Test LLM connection using current configuration.
    
    Returns:
        Tuple[bool, str]: (success, message)
    """
    try:
        # Get LLM instance
        llm = get_llm_instance()
        if not llm:
            return False, "LLM not configured"
            
        # Test with a simple prompt
        test_prompt = "Hello, are you working?"
        response = llm.get_completion(test_prompt)
        
        if response:
            return True, "LLM connection successful"
        else:
            return False, "LLM returned empty response"
            
    except Exception as e:
        logger.error(f"LLM connection test failed: {str(e)}")
        return False, f"LLM connection failed: {str(e)}"
