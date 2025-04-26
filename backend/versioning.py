import datetime
import logging
from backend.sql_connector import SQLConnector

def log_change(sql_query: str, description: str = ""):
    """
    Logs a database change to an AuditLog table.
    
    The AuditLog table should be pre-created in your database with at least the following columns:
    - Id (auto-incremented primary key)
    - Timestamp
    - QueryText
    - Description
    """
    connector = SQLConnector()
    timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    insert_query = """
    INSERT INTO AuditLog (Timestamp, QueryText, Description)
    VALUES (?, ?, ?)
    """
    params = (timestamp, sql_query, description)
    try:
        connector.execute_query(insert_query, params)
        logging.info("Successfully logged change.")
    except Exception as e:
        logging.error(f"Error logging change: {e}")
        raise
    finally:
        connector.close_connection()

if __name__ == "__main__":
    # Quick test of the audit logging function.
    test_sql = "UPDATE Customers SET Status = 'active' WHERE CustomerId = 123"
    log_change(test_sql, "Test audit log entry")
    print("Change logged successfully.")
