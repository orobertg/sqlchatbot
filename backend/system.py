"""
System Configuration Module
Handles core system settings and configuration
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Any, Tuple
import pyodbc
import requests

logger = logging.getLogger(__name__)

# Get project root directory
PROJECT_ROOT = Path(__file__).parent.parent
logger.info(f"Project root: {PROJECT_ROOT}")

# Load environment variables from .env file
ENV_PATH = PROJECT_ROOT / '.env'
logger.info(f"Looking for .env file at: {ENV_PATH}")

logger.info("Loading environment variables...")
load_dotenv(ENV_PATH)

def get_db_config() -> Dict[str, Any]:
    """
    Get database configuration from environment variables.
    
    Returns:
        Dict[str, Any]: Database configuration dictionary
    """
    # Default to Connection String mode if not specified
    connection_mode = os.getenv("CONNECTION_MODE", "Connection String")
    
    if connection_mode == "ODBC DSN":
        dsn = os.getenv("DATABASE_DSN")
        if not dsn:
            # Fall back to Connection String mode if DSN is not configured
            connection_mode = "Connection String"
        else:
            return {
                "mode": "DSN",
                "dsn": dsn,
                "user": os.getenv("DATABASE_USER", ""),
                "password": os.getenv("DATABASE_PASSWORD", "")
            }
    
    # Use Connection String mode
    return {
        "mode": "CONNECTION_STRING",
        "server": os.getenv("DATABASE_SERVER", ""),
        "database": os.getenv("DATABASE_NAME", ""),
        "user": os.getenv("DATABASE_USER", ""),
        "password": os.getenv("DATABASE_PASSWORD", "")
    }

def test_db_connection() -> Tuple[bool, str]:
    """Test database connection using current configuration."""
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
                f"DATABASE={DB_CONFIG['database']};"
                f"UID={DB_CONFIG['user']};"
                f"PWD={DB_CONFIG['password']}"
            )
        
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        return True, "Database connection successful"
    except Exception as e:
        logger.error(f"Database connection test failed: {str(e)}")
        return False, f"Database connection failed: {str(e)}"

# Export the database config
try:
    DB_CONFIG = get_db_config()
    logger.info(f"Using database config: {DB_CONFIG | {'password': '*****'}}")
except Exception as e:
    logger.error(f"Failed to load database configuration: {e}")
    raise

# LLM Configuration
LLM_CONFIG = {
    'model': os.getenv("LLM_MODEL", "qwen2.5-coder:7b"),
    'api_base': os.getenv("OPENAI_API_BASE", "http://localhost:11434/").rstrip("/") + "/",
    'api_key': os.getenv("OPENAI_API_KEY", "ollama")
}

def test_llm_connection() -> Tuple[bool, str]:
    """Test LLM connection using current configuration."""
    try:
        base_url = LLM_CONFIG['api_base'].rstrip("/")
        if base_url.endswith("/v1"):
            base_url = base_url[:-3].rstrip("/")
        
        # First test if Ollama API is accessible
        try:
            response = requests.get(f"{base_url}/api/tags")
            response.raise_for_status()
        except Exception as e:
            return False, f"Could not connect to Ollama API: {str(e)}"
        
        # Then test if the model is available and working
        try:
            # Prepare a simple test request
            headers = {
                "Content-Type": "application/json"
            }
            
            data = {
                "model": LLM_CONFIG['model'],
                "messages": [{"role": "user", "content": "Hello, are you working?"}],
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "top_p": 0.1,
                    "num_predict": 10  # Keep it short for testing
                }
            }
            
            # Make request to Ollama's chat endpoint
            response = requests.post(
                f"{base_url}/api/chat",
                headers=headers,
                json=data,
                timeout=10  # Add timeout to prevent hanging
            )
            response.raise_for_status()
            
            # Check if we got a valid response
            result = response.json()
            if not result.get('message', {}).get('content'):
                return False, "Model returned empty response"
                
            return True, "LLM connection and model test successful"
            
        except requests.exceptions.Timeout:
            return False, "Model test timed out - the model might be too slow or not responding"
        except Exception as e:
            return False, f"Model test failed: {str(e)}"
            
    except Exception as e:
        logger.error(f"LLM connection test failed: {str(e)}")
        return False, f"LLM connection failed: {str(e)}"

# Logging configuration
LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        },
    },
    "handlers": {
        "default": {
            "level": "INFO",
            "formatter": "standard",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "": {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": True
        }
    }
}

def get_status_emoji(status: bool) -> str:
    """Get status emoji based on status."""
    return "🟢" if status else "🔴"

def get_system_status() -> Tuple[bool, bool]:
    """
    Get system status for database and LLM connections.
    
    Returns:
        Tuple[bool, bool]: (database_status, llm_status)
    """
    db_status, _ = test_db_connection()
    llm_status, _ = test_llm_connection()
    return db_status, llm_status

# Future system-related functions could include:
# - System health metrics
# - Resource usage monitoring
# - Configuration validation
# - System initialization checks
# - Cross-component coordination 