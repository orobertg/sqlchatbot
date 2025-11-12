from typing import Dict, Any
from backend.db_tools import (
    ListTablesInput, ListTablesOutput,
    DescribeTableInput, DescribeTableOutput,
    ExecuteQueryInput, ExecuteQueryOutput,
    list_tables, describe_table, execute_query,
    is_destructive_query
)

class BaseTool:
    """Base class for all tools"""
    def __call__(self, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError

class QueryTool(BaseTool):
    """Tool for executing queries"""
    def __init__(self, allow_destructive: bool = False):
        self.allow_destructive = allow_destructive
        
    def __call__(self, query: str, **kwargs) -> Dict[str, Any]:
        if not self.allow_destructive and is_destructive_query(query):
            return {"error": "Destructive queries not allowed"}
        return execute_query(ExecuteQueryInput(query=query)).dict()

class SchemaMapTool(BaseTool):
    """Tool for schema operations"""
    def __call__(self, table_name: str, schema_name: str = None, **kwargs) -> Dict[str, Any]:
        return describe_table(
            DescribeTableInput(table_name=table_name, schema_name=schema_name)
        ).dict()

# Tools in OpenAI-compatible format
TOOL_DEFS = [
    {
        "type": "function",
        "function": {
            "name": "list_tables",
            "description": "List all tables in the database.",
            "parameters": ListTablesInput.model_json_schema()
        }
    },
    {
        "type": "function",
        "function": {
            "name": "describe_table",
            "description": "Describe columns in a given table.",
            "parameters": DescribeTableInput.model_json_schema()
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_query",
            "description": "Execute an arbitrary SQL query.",
            "parameters": ExecuteQueryInput.model_json_schema()
        }
    }
]

def route_tool(name: str, arguments: dict) -> Dict[str, Any]:
    """Route tool calls to appropriate handlers"""
    tools = {
        "list_tables": lambda **kwargs: list_tables(ListTablesInput(**kwargs)).dict(),
        "describe_table": SchemaMapTool(),
        "execute_query": QueryTool(allow_destructive=False)
    }
    
    if name not in tools:
        raise ValueError(f"Unknown tool: {name}")
        
    return tools[name](**arguments) 