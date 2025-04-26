import logging
import time
import re
from backend.llm_engine import generate_sql as generate_sql_query
from backend.sql_connector import SQLConnector
from backend.versioning import log_change
from backend.audit_logger import log_query_event

DESTRUCTIVE_KEYWORDS = ["UPDATE", "INSERT", "DELETE", "DROP", "ALTER"]

def is_destructive(query: str) -> bool:
    """
    Check if the provided SQL query might modify data.
    """
    upper_query = query.upper()
    return any(keyword in upper_query for keyword in DESTRUCTIVE_KEYWORDS)

def clean_sql_backticks(sql: str) -> str:
    """
    Remove Markdown-style triple backtick blocks if present.
    """
    return re.sub(r"^```sql\s*|```$", "", sql.strip(), flags=re.IGNORECASE)

def process_user_prompt(user_prompt: str, execute_query: bool = False, confirm_destructive: bool = False):
    """
    Processes the user prompt:
      - Generates SQL using the LLM.
      - Returns SQL preview, and raw reasoning by default.
      - Executes SQL if requested and confirmed (if destructive).
    Returns:
      result | raw_llm_output | prompt
    """
    sql_query, raw_llm_output, full_prompt = generate_sql_query(user_prompt)
    sql_query = clean_sql_backticks(sql_query)
    logging.info(f"Generated SQL: {sql_query}")

    if not execute_query:
        return sql_query, raw_llm_output, full_prompt

    if is_destructive(sql_query) and not confirm_destructive:
        return (
            "-- The generated SQL appears to be data-modifying. "
            "Please confirm execution by checking the appropriate option.",
            raw_llm_output,
            full_prompt
        )

    connector = None
    start = time.time()
    try:
        connector = SQLConnector()
        result = connector.execute_query(sql_query)
        duration = int((time.time() - start) * 1000)

        log_query_event(
            user_prompt=user_prompt,
            generated_sql=sql_query,
            success=True,
            execution_time_ms=duration
        )

        if is_destructive(sql_query):
            log_change(sql_query, description="Executed change generated from prompt")
            logging.info("Change logged for audit purposes.")

        if result is None:
            return "✅ Query executed successfully. No result set to display.", raw_llm_output, full_prompt
        elif isinstance(result, list):
            return result, raw_llm_output, full_prompt
        else:
            return str(result), raw_llm_output, full_prompt

    except Exception as e:
        logging.error(f"Error executing query: {e}")

        log_query_event(
            user_prompt=user_prompt,
            generated_sql=sql_query,
            success=False,
            error_message=str(e)
        )

        return f"Error executing query: {e}", raw_llm_output, full_prompt

    finally:
        if connector:
            connector.close_connection()

if __name__ == "__main__":
    test_prompt = "Show me the total sales from the orders table for last quarter where the status is complete."
    sql, output, prompt = process_user_prompt(test_prompt, execute_query=False)
    print("SQL Preview:\n", sql)
    print("Prompt:\n", prompt)
    print("LLM Output:\n", output)
