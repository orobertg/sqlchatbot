import sqlite3
import os
from pathlib import Path
from datetime import datetime
import logging
from typing import Optional, Dict, Any
from backend.sql_connector import SQLConnector
import json

logger = logging.getLogger(__name__)

AUDIT_FOLDER = Path("data/audit")
AUDIT_FOLDER.mkdir(parents=True, exist_ok=True)
AUDIT_DB_PATH = AUDIT_FOLDER / "chat_audit.db"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS query_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    user_prompt TEXT,
    generated_sql TEXT,
    success INTEGER,
    error_message TEXT,
    execution_time_ms INTEGER
);
"""

class AuditLogger:
    def __init__(self, log_file='audit_log.json'):
        self.logger = logging.getLogger(__name__)
        self.log_file = Path('logs') / log_file
        
        # Ensure logs directory exists
        self.log_file.parent.mkdir(exist_ok=True)
        
        # Create log file if it doesn't exist
        if not self.log_file.exists():
            self.log_file.write_text('[]')
        
    def log_query_event(self, query, params=None, user="system", status="completed", row_count=None, error=None):
        """Log a query event to the audit log.
        
        Args:
            query (str): The SQL query that was executed
            params (dict, optional): Query parameters
            user (str): User who executed the query
            status (str): Status of the query (started/completed/failed)
            row_count (int, optional): Number of rows affected/returned
            error (str, optional): Error message if query failed
        """
        try:
            # Read existing logs
            logs = self._read_logs()
            
            # Create new log entry
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "user": user,
                "query": query,
                "parameters": params,
                "status": status,
                "row_count": row_count,
                "error": error
            }
            
            # Add new entry and write back
            logs.append(log_entry)
            self._write_logs(logs)
            
        except Exception as e:
            self.logger.error(f"Failed to log query event: {str(e)}")
    
    def get_logs(self, limit=None, status=None, user=None):
        """Get audit logs with optional filtering.
        
        Args:
            limit (int, optional): Maximum number of logs to return
            status (str, optional): Filter by status
            user (str, optional): Filter by user
        
        Returns:
            list: List of log entries
        """
        try:
            logs = self._read_logs()
            
            # Apply filters
            if status:
                logs = [log for log in logs if log.get('status') == status]
            if user:
                logs = [log for log in logs if log.get('user') == user]
            
            # Apply limit
            if limit:
                logs = logs[-limit:]
                
            return logs
        except Exception as e:
            self.logger.error(f"Failed to get logs: {str(e)}")
            return []
    
    def _read_logs(self):
        """Read logs from file."""
        try:
            return json.loads(self.log_file.read_text())
        except Exception as e:
            self.logger.error(f"Failed to read logs: {str(e)}")
            return []
    
    def _write_logs(self, logs):
        """Write logs to file."""
        try:
            self.log_file.write_text(json.dumps(logs, indent=2))
        except Exception as e:
            self.logger.error(f"Failed to write logs: {str(e)}")

def init_audit_log():
    """
    Ensures that the audit database and table exist.
    """
    try:
        with sqlite3.connect(AUDIT_DB_PATH) as conn:
            conn.execute('PRAGMA journal_mode=WAL;')  # 🧠 Enable fast non-blocking writes
            conn.execute(CREATE_TABLE_SQL)
            conn.commit()
        logger.info("[AuditLogger] Initialized audit DB at %s", AUDIT_DB_PATH)
    except Exception as e:
        logger.warning("[AuditLogger] Could not initialize audit log: %s", e)

def log_query_event(user_prompt: str, generated_sql: str, success: bool, error_message: str = None, execution_time_ms: int = None):
    """
    Log a query event safely and synchronously to the audit log.
    """
    try:
        with sqlite3.connect(AUDIT_DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO query_audit_log
                (timestamp, user_prompt, generated_sql, success, error_message, execution_time_ms)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now().isoformat(timespec="seconds"),
                    user_prompt,
                    generated_sql,
                    1 if success else 0,
                    error_message,
                    execution_time_ms
                )
            )
            conn.commit()
        logger.info("[AuditLogger] Logged query event successfully.")
    except Exception as e:
        logger.warning("[AuditLogger] Failed to log query event: %s", e)

def fetch_recent_audit_logs(limit: int = 50):
    """
    Retrieves the N most recent audit logs.
    """
    try:
        with sqlite3.connect(AUDIT_DB_PATH) as conn:
            cursor = conn.execute(
                """
                SELECT timestamp, user_prompt, generated_sql, success, error_message, execution_time_ms
                FROM query_audit_log
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,)
            )
            rows = cursor.fetchall()

            entries = []
            for row in rows:
                entries.append({
                    "Timestamp": row[0],
                    "User Prompt": row[1],
                    "Generated SQL": row[2],
                    "Success": row[3],
                    "Error Message": row[4],
                    "Duration (ms)": row[5],
                })
            return entries
    except Exception as e:
        logger.error("[AuditLogger] Failed to fetch logs: %s", e)
        return []

def log_chat_interaction(
    user_input: str,
    generated_sql: str,
    full_prompt: str = None,
    raw_model_response: str = None,
    database_used: str = None,
    schema_used: str = None,
    fix_info: str = None,
    execution_time: float = None
):
    # Optional: add proper logging logic here (e.g. save to DB or file)
    logging.info("[Audit] User input: %s", user_input)
    logging.info("[Audit] Generated SQL: %s", generated_sql)
    logging.info("[Audit] Database: %s, Schema: %s", database_used, schema_used)
    logging.info("[Audit] Execution time: %s seconds", execution_time)
    if fix_info:
        logging.info("[Audit] Fix Info: %s", fix_info)
