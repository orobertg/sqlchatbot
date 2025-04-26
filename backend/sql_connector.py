import pyodbc
import logging
from config.database_config import load_database_config

class SQLConnector:
    """
    A connector class for interacting with an MS SQL database.
    """
    def __init__(self):
        self.config = load_database_config()
        connection_mode = (self.config.get("CONNECTION_MODE") or "MANUAL").strip().upper()
        logging.info(f"[SQLConnector] Connection mode: {connection_mode}")

        logging.info(f"[SQLConnector] DATABASE_CONFIG values:")        
        for key, value in self.config.items():
            display_value = "********" if "password" in key.lower() else value
            logging.info(f"  {key}: {display_value}")    

        if connection_mode == "ODBC_DSN":
            dsn = self.config.get("DATABASE_DSN", "").strip()
            if not dsn:
                raise Exception("DATABASE_DSN not set in configuration for ODBC DSN mode.")
            connection_string = f"DSN={dsn};UID={self.config.get('user')};PWD={self.config.get('password')};"
        else:
            driver = self.config.get('driver') or self.config.get('DATABASE_DRIVER')
            if not driver:
                raise Exception("DATABASE_DRIVER not set in configuration.")
            driver = driver.strip()
            if not (driver.startswith("{") and driver.endswith("}")):
                driver = "{" + driver + "}"

            server = self.config.get('server', '').strip()
            if server.lower().startswith("tcp:"):
                server = server.replace("tcp:", "")
            port = self.config.get('port', '').strip()
            if port:
                server = f"{server},{port}"

            connection_string = (
                f"DRIVER={driver};"
                f"SERVER={server};"
                f"DATABASE={self.config.get('database')};"
                f"UID={self.config.get('user')};"
                f"PWD={self.config.get('password')};"
            )

        safe_connection_string = connection_string.replace(
            f"PWD={self.config.get('password')};", "PWD=********;"
        )
        print(f"[SQLConnector] Connecting with: {safe_connection_string}")
        logging.info(f"[SQLConnector] Connecting with: {safe_connection_string}")

        try:
            self.conn = pyodbc.connect(connection_string)
            self.cursor = self.conn.cursor()
            logging.info("Connected to MS SQL database successfully.")
        except Exception as e:
            logging.error(f"Failed to connect to database: {e}")
            raise

    def execute_query(self, query: str, params=None):
        try:
            logging.info(f"[SQLConnector] Executing query: {query}")
            if params is None:
                self.cursor.execute(query)
            else:
                self.cursor.execute(query, params)

            if query.strip().lower().startswith("select"):
                rows = self.cursor.fetchall()
                logging.info(f"[SQLConnector] Query returned {len(rows)} rows.")
                return rows
            else:
                self.conn.commit()
                logging.info("[SQLConnector] Non-select query committed.")
                return []
        except Exception as e:
            self.conn.rollback()
            logging.error(f"Error executing query: {e}")
            raise

    def close_connection(self):
        self.conn.close()
        logging.info("[SQLConnector] Connection closed.")

def validate_db_connection() -> bool:
    try:
        connector = SQLConnector()
        test_result = connector.execute_query("SELECT 1 AS test")
        connector.close_connection()
        return True
    except Exception as e:
        print(f"Database connection test error: {e}")
        return False
