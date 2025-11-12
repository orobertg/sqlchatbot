"""
SQL Connector Module
Handles database connections and query execution
"""

import pyodbc
import logging
import os
from dotenv import load_dotenv
from typing import Optional, Any, List, Dict, Tuple
from backend.system import DB_CONFIG

# Configure logging
logger = logging.getLogger("backend.sql_connector")

# Load environment variables
load_dotenv()

class SQLConnector:
    """SQL Server connection handler"""
    
    def __init__(self, database: str = None):
        """Initialize connection with optional database override"""
        self.conn = None
        self.cursor = None
        self.connect(database)
    
    def connect(self, database: str = None) -> None:
        """Establish database connection"""
        try:
            if DB_CONFIG["mode"] == "DSN":
                conn_str = (
                    f"DSN={DB_CONFIG['dsn']};"
                    f"UID={DB_CONFIG['user']};"
                    f"PWD={DB_CONFIG['password']}"
                )
            else:
                conn_str = (
                    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                    f"SERVER={DB_CONFIG['server']};"
                    f"DATABASE={database or DB_CONFIG['database']};"
                    f"UID={DB_CONFIG['user']};"
                    f"PWD={DB_CONFIG['password']}"
                )
            
            self.conn = pyodbc.connect(conn_str)
            self.cursor = self.conn.cursor()
            logger.info("Database connection established successfully")
            
        except Exception as e:
            logger.error(f"Database connection failed: {str(e)}")
            raise
    
    def close(self) -> None:
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")
    
    def execute_query(self, query: str, params: List = None) -> Tuple[List[str], List[dict]]:
        """
        Execute SQL query and return results as list of dictionaries
        
        Args:
            query (str): SQL query to execute
            params (List, optional): Query parameters
            
        Returns:
            Tuple[List[str], List[dict]]: Column names and results as dicts
        """
        try:
            self.cursor.execute(query, params or [])
            # Get column names
            columns = [column[0] for column in self.cursor.description] if self.cursor.description else []
            # Fetch results
            results = self.cursor.fetchall()
            # Convert all rows to dicts using dict(zip(columns, row))
            dict_results = []
            for row in results:
                if isinstance(row, dict):
                    dict_results.append(row)
                else:
                    dict_results.append(dict(zip(columns, row)))
            # Ensure we always return both columns and results
            if not columns and dict_results:
                # For COUNT queries, use a default column name
                columns = ['count']
            return columns, dict_results
        except Exception as e:
            logger.error(f"Query execution failed: {str(e)}")
            logger.error(f"Query: {query}")
            logger.error(f"Parameters: {params}")
            raise

    def get_databases(self):
        """Get list of available databases."""
        try:
            if not self.conn:
                self.connect()
            
            cursor = self.conn.cursor()
            cursor.execute("SELECT name FROM sys.databases WHERE database_id > 4")  # Skip system DBs
            return [row.name for row in cursor.fetchall()]
            
        except Exception as e:
            error_msg = f"Error getting databases: {str(e)}"
            logger.error(f"[SQLConnector] {error_msg}")
            raise

    def is_connected(self) -> bool:
        """Check if connection is valid"""
        if not self.conn:
            return False
        try:
            # Test the connection
            self.conn.execute("SELECT 1")
            return True
        except:
            return False

    def cursor(self):
        """Get a cursor, creating connection if needed"""
        if not self.is_connected():
            if not self.connect():
                raise Exception("No valid SQL database connection found. Please configure your database settings.")
        
        if not self.conn:
            self.conn = pyodbc.connect(DB_CONFIG.get('CONNECTION_STRING'))
        return self.conn.cursor()
    
    @property
    def messages(self):
        """Get messages from the cursor"""
        if self.conn:
            return self.conn.messages
        return []

    def __del__(self):
        """Cleanup connection on object destruction"""
        try:
            if hasattr(self, 'conn') and self.conn:
                self.conn.close()
        except:
            pass  # Silently handle cleanup errors

def validate_db_connection(database_override: Optional[str] = None) -> bool:
    try:
        connector = SQLConnector()
        conn = connector.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 AS test")
        result = cursor.fetchone()
        conn.close()
        return result is not None
    except Exception as e:
        logging.warning(f"Database connection test failed: {e}")
        return False
    
def execute_sql_query(query: str, params: List = None) -> Tuple[List[str], List[dict]]:
    """
    Execute SQL query using a temporary connection
    
    Args:
        query (str): SQL query to execute
        params (List, optional): Query parameters
        
    Returns:
        Tuple[List[str], List[dict]]: Column names and results as dicts
    """
    connector = SQLConnector()
    try:
        return connector.execute_query(query, params)
    finally:
        connector.close()

def mask_sensitive_info(config: Dict[str, Any]) -> Dict[str, Any]:
    """Mask sensitive information in configuration for logging."""
    masked_config = config.copy()
    sensitive_keys = ['password', 'PWD', 'PASSWORD', 'pwd']
    
    for key in sensitive_keys:
        if key in masked_config:
            masked_config[key] = '*****'
    
    return masked_config

def get_db_connection():
    """Get a database connection."""
    try:
        connection_mode = os.environ.get("CONNECTION_MODE", "Connection String")
        
        # Create config dict for logging
        config = {
            'mode': connection_mode,
            'driver': os.environ.get('DATABASE_DRIVER'),
            'server': os.environ.get('DATABASE_SERVER'),
            'database': os.environ.get('DATABASE_NAME'),
            'username': os.environ.get('DATABASE_USER'),
            'password': os.environ.get('DATABASE_PASSWORD'),
            'port': os.environ.get('DATABASE_PORT', '1433'),
        }
        
        # Log masked configuration
        logger.debug(f"Using database config: {mask_sensitive_info(config)}")
        
        if connection_mode == "ODBC DSN":
            dsn = os.environ.get("DATABASE_DSN")
            username = os.environ.get("DATABASE_USER")
            password = os.environ.get("DATABASE_PASSWORD")
            
            if not dsn:
                raise ValueError("DSN not configured")
                
            logger.debug(f"Attempting DSN connection with: DSN={dsn}, UID={username}")
            conn_str = (
                f"DSN={dsn};"
                f"UID={username};"
                f"PWD={password}"
            )
            return pyodbc.connect(conn_str)
        else:
            logger.debug(f"Attempting connection with: Driver={config['driver']}, Server={config['server']}, Database={config['database']}, UID={config['username']}")
            
            conn_str = (
                f"Driver={config['driver']};"
                f"Server={config['server']};"
                f"Database={config['database']};"
                f"UID={config['username']};"
                f"PWD={config['password']}"
            )
            return pyodbc.connect(conn_str)
    except Exception as e:
        logger.error(f"Failed to connect to database: {str(e)}")
        raise

def test_db_connection() -> Tuple[bool, str]:
    """
    Test database connection based on current configuration mode.
    
    Returns:
        Tuple[bool, str]: (success, message)
    """
    try:
        # Get current connection mode
        mode = os.getenv("CONNECTION_MODE", "").strip()
        
        # Validate based on connection mode
        if mode == "Connection String":
            conn_string = os.getenv("DATABASE_CONNECTION_STRING")
            if not conn_string:
                return False, "No connection string configured. Please save your connection string settings first."
                
            # Test the connection string
            connector = SQLConnector(connection_string=conn_string)
            
        elif mode == "DSN":
            dsn = os.getenv("DATABASE_DSN")
            if not dsn:
                return False, "No DSN configured. Please save your DSN settings first."
                
            # Test the DSN connection
            connector = SQLConnector(dsn=dsn)
            
        else:
            return False, "Please configure and save your database connection settings first."
        
        # Test the connection
        try:
            connector.connect()
            connector.close()
            return True, "Database connection successful"
        except Exception as e:
            return False, f"Connection failed: {str(e)}"
            
    except Exception as e:
        return False, f"Error testing connection: {str(e)}"