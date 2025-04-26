# tool_registry.py
from tools import (
    list_tables, describe_table, execute_query,
    ListTablesInput, ListTablesOutput,
    DescribeTableInput, DescribeTableOutput,
    ExecuteQueryInput, ExecuteQueryOutput
)

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

# Tool execution router
def route_tool(name: str, arguments: dict):
    if name == "list_tables":
        return list_tables(ListTablesInput(**arguments))
    elif name == "describe_table":
        return describe_table(DescribeTableInput(**arguments))
    elif name == "execute_query":
        return execute_query(ExecuteQueryInput(**arguments))
    else:
        raise ValueError(f"Unknown tool: {name}")
