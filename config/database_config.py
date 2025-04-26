# config/database_config.py

import os
from dotenv import load_dotenv

def load_database_config():
    """
    Reloads the .env file and returns the latest database configuration.
    This should be used dynamically before connecting to the database.
    """
    load_dotenv(override=True)
    return {
        'driver': os.getenv('DATABASE_DRIVER', ''),
        'server': os.getenv('DATABASE_SERVER', ''),
        'database': os.getenv('DATABASE_NAME', ''),
        'user': os.getenv('DATABASE_USER', ''),
        'password': os.getenv('DATABASE_PASSWORD', ''),
        'port': os.getenv('DATABASE_PORT', '1433'),
        'connection_mode': os.getenv('CONNECTION_MODE', 'MANUAL'),
        'dsn': os.getenv('DATABASE_DSN', '')
    }

# Fallback snapshot at import time
DATABASE_CONFIG = load_database_config()

