import sqlite3
import os
from pathlib import Path
from datetime import datetime
import logging

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
