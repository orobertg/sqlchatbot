import pyodbc
import os
import logging
from config.database_config import load_database_config

logger = logging.getLogger(__name__)

class SQLConnector:
    def __init__(self, database_override: str = None):
        self.config = load_database_config()
        self.connection = None
        self.database_override = database_override  # ✅ Allow dynamic database override

    def connect(self):
        """
        Establish a new database connection based on .env settings or override.
        """
        try:
            mode = self.config.get("connection_mode", "MANUAL").upper()

            if mode == "ODBC_DSN":
                dsn = self.config.get("database_dsn", "").strip()
                uid = self.config.get("user", "").strip()
                pwd = self.config.get("password", "").strip()
                conn_str = f"DSN={dsn};UID={uid};PWD={pwd}"
            else:  # MANUAL connection string
                driver = self.config.get("driver", "").strip()
                server = self.config.get("server", "").strip()
                port = self.config.get("port", "").strip()
                # ✅ If database_override is given, use it instead of .env database
                database = self.database_override or self.config.get("database", "").strip()
                uid = self.config.get("user", "").strip()
                pwd = self.config.get("password", "").strip()

                if not server.lower().startswith("tcp:"):
                    server = f"tcp:{server}"

                server_and_port = f"{server},{port}" if port else server

                conn_str = (
                    f"DRIVER={driver};"
                    f"SERVER={server_and_port};"
                    f"DATABASE={database};"
                    f"UID={uid};"
                    f"PWD={pwd};"
                )

            logger.info(f"[SQLConnector] Connecting with: {conn_str.replace(pwd, '********')}")
            self.connection = pyodbc.connect(conn_str)
            logger.info(f"[SQLConnector] Successfully connected to database: {self.database_override or self.config.get('database')}")

        except Exception as e:
            logger.error(f"[SQLConnector] Failed to connect to database: {e}")
            raise

    def close_connection(self):
        """
        Safely close the database connection.
        """
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("[SQLConnector] Database connection closed.")

    def execute_query(self, sql_query: str, database_override: str = None):
        """
        Execute a SQL query and return results.
        If database_override is provided at query-time, force reconnect.
        """
        # ✅ Handle dynamic override at query-time too
        if database_override and (database_override != self.database_override):
            self.database_override = database_override
            self.connection = None  # Force re-connect

        if not self.connection:
            self.connect()

        try:
            cursor = self.connection.cursor()
            logger.info(f"[SQLConnector] Executing query:\n{sql_query}")

            cursor.execute(sql_query)

            if cursor.description:
                columns = [column[0] for column in cursor.description]
                rows = cursor.fetchall()
                results = [dict(zip(columns, row)) for row in rows]
                logger.info(f"[SQLConnector] Query returned {len(results)} rows.")
                return results
            else:
                logger.info("[SQLConnector] Query executed successfully (no result set).")
                return []

        except Exception as e:
            logger.error(f"[SQLConnector] Query execution failed: {e}")
            raise

def validate_db_connection() -> bool:
    """
    Validate if a database connection can be established.
    Always uses the default database in .env configuration.
    """
    try:
        config = load_database_config()
        default_db = config.get("database", "unknown")

        connector = SQLConnector()
        test_result = connector.execute_query("SELECT 1 AS test")
        connector.close_connection()

        logger.info(f"[SQLConnector] Database connection validation succeeded (Database: {default_db})")
        return True

    except Exception as e:
        logger.error(f"[SQLConnector] Database connection validation FAILED (Database: {default_db}): {e}")
        return False

