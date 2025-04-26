import streamlit as st
import os,sys
from pathlib import Path
from dotenv import load_dotenv, set_key, dotenv_values
import requests  # For retrieving available models
from backend.tools import get_schema_map_tool
from backend.llm_engine import set_llm_instance
from backend.sql_connector import SQLConnector
import pandas as pd

# Load environment variables and locate the .env file.
load_dotenv()
env_path = Path('.') / '.env'

# Define the configuration keys.
CONFIG_KEYS = [
    "LLM_MODEL", 
    "OPENAI_API_BASE",    # Base URL for the OpenAI client (e.g., http://localhost:11434/)
    "OPENAI_API_KEY",     # API key for the OpenAI client
    "CONNECTION_MODE",    # "MANUAL" or "ODBC_DSN"
    "DATABASE_DRIVER",    # Used only in MANUAL mode
    "DATABASE_SERVER",    # Used only in MANUAL mode
    "DATABASE_NAME",      # Used only in MANUAL mode
    "DATABASE_USER",      # Used in both modes
    "DATABASE_PASSWORD",  # Used in both modes
    "DATABASE_PORT",      # Used only in MANUAL mode
    "DATABASE_DSN"        # Used only in ODBC_DSN mode
]

def get_config():
    """Return a dictionary of the current configuration values read from the .env file."""
    config = dotenv_values(str(env_path))
    return {key: config.get(key, "") for key in CONFIG_KEYS}

def build_connection_string(config: dict) -> str:
    """
    Build the database connection string.
    
    For ODBC_DSN mode, returns:
      DSN=[DATABASE_DSN];UID=[DATABASE_USER];PWD=[DATABASE_PASSWORD];
    For MANUAL mode, returns a string with DRIVER, SERVER (with tcp: prefix and port appended),
      DATABASE, UID, and PWD.
    """
    mode = config.get("CONNECTION_MODE", "MANUAL").strip().upper()
    
    if mode == "ODBC_DSN":
        dsn = config.get("DATABASE_DSN", "").strip()
        if not dsn:
            return "DSN not configured."
        connection_string = (
            f"DSN={dsn};"
            f"UID={config.get('DATABASE_USER', '').strip()};"
            f"PWD={config.get('DATABASE_PASSWORD', '').strip()};"
        )
    else:
        driver = config.get("DATABASE_DRIVER", "").strip()
        if not (driver.startswith("{") and driver.endswith("}")):
            driver = "{" + driver + "}"
        
        server = config.get("DATABASE_SERVER", "").strip()
        if not server.lower().startswith("tcp:"):
            server = "tcp:" + server
        port = config.get("DATABASE_PORT", "").strip()
        if port:
            server = f"{server},{port}"
        
        connection_string = (
            f"DRIVER={driver};"
            f"SERVER={server};"
            f"DATABASE={config.get('DATABASE_NAME', '').strip()};"
            f"UID={config.get('DATABASE_USER', '').strip()};"
            f"PWD={config.get('DATABASE_PASSWORD', '').strip()};"
        )
        safe_connection_string = connection_string.replace(
            f"PWD={config.get('DATABASE_PASSWORD')};", 
            "PWD=********;"
        )
    return safe_connection_string

def display_config_table(config: dict):
    """Display the current configuration and constructed connection string."""
    st.subheader(":ocean: Current Configuration")
    table_md = "| Key | Value |\n| --- | --- |\n"
    for key, value in config.items():
        if key == "DATABASE_PASSWORD" and value:
            value = "*" * len(value)
        table_md += f"| {key} | {value} |\n"
    st.markdown(table_md)
    
    st.subheader(":oil_drum: DB Connection String")
    connection_string = build_connection_string(config)
    st.code(connection_string, language="markdown")

def get_available_models():
    """
    Retrieve available model names from the local endpoint.
    Uses the OPENAI_API_BASE from the .env file and ensures no trailing '/v1'.
    """
    try:
        base_url = os.getenv("OPENAI_API_BASE", "http://localhost:11434/").rstrip("/")
        if base_url.endswith("/v1"):
            base_url = base_url[:-3].rstrip("/")
        url = f"{base_url}/api/tags" 
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        models = [m["name"] for m in data.get("models", [])]
        return models
    except Exception as e:
        st.error(f"Error retrieving available models: {e}")
        return []

def test_model_connection(model_name: str) -> bool:
    """
    Attempts to create a chat session with the given model.
    Returns True if successful, otherwise False.
    """
    try:
        set_llm_instance(model_name)
        return True
    except Exception as e:
        st.error(f"LLM Connection test failed: {e}")
        return False

def main():
    st.title(":globe_with_meridians: Application Settings")
    
    current_config = get_config()
    display_config_table(current_config)
    
    st.header(":abacus: Update Configuration")
    current_mode = current_config.get("CONNECTION_MODE", "MANUAL").strip().upper() or "MANUAL"
    connection_mode = st.radio(
        "Connection Mode", 
        options=["MANUAL", "ODBC_DSN"], 
        index=0 if current_mode == "MANUAL" else 1,
        help="Select 'MANUAL' to specify connection fields individually, or 'ODBC_DSN' to use an existing ODBC DSN."
    )
    
    # LLM Model and OpenAI API settings.
    new_llm_model = st.text_input("LLM Model", value=current_config.get("LLM_MODEL", ""))
    new_open_api_base = st.text_input("OPENAI API Base URL", value=current_config.get("OPENAI_API_BASE", "http://localhost:11434/"))
    new_open_api_key = st.text_input("OPENAI API KEY", value=current_config.get("OPENAI_API_KEY", ""))
    
    if connection_mode == "MANUAL":
        new_db_driver = st.text_input("Database Driver", value=current_config.get("DATABASE_DRIVER", "{ODBC Driver 17 for SQL Server}"))
        new_db_server = st.text_input("Database Server", value=current_config.get("DATABASE_SERVER", ""))
        new_db_name = st.text_input("Database Name", value=current_config.get("DATABASE_NAME", ""))
        new_db_user = st.text_input("Database User", value=current_config.get("DATABASE_USER", ""))
        new_db_password = st.text_input("Database Password", value=current_config.get("DATABASE_PASSWORD", ""), type="password")
        new_db_port = st.text_input("Database Port", value=current_config.get("DATABASE_PORT", ""))
    else:
        new_db_dsn = st.text_input("ODBC DSN Name", value=current_config.get("DATABASE_DSN", ""))
        new_db_user = st.text_input("Database User", value=current_config.get("DATABASE_USER", ""))
        new_db_password = st.text_input("Database Password", value=current_config.get("DATABASE_PASSWORD", ""), type="password")
    
    available_models = get_available_models()
    if new_llm_model.strip() not in available_models:
        st.error("The entered LLM model is not available. Please select from the list below:")
        selected_model = st.selectbox("Available LLM Models", available_models)
        new_llm_model = selected_model
    else:
        st.success("Entered LLM model is valid.")
    
    if st.button("Update Settings"):
        set_key(str(env_path), "LLM_MODEL", new_llm_model.strip())
        set_key(str(env_path), "OPENAI_API_BASE", new_open_api_base.strip())
        set_key(str(env_path), "OPENAI_API_KEY", new_open_api_key.strip())
        set_key(str(env_path), "CONNECTION_MODE", connection_mode)
        
        if connection_mode == "MANUAL":
            set_key(str(env_path), "DATABASE_DRIVER", new_db_driver.strip())
            set_key(str(env_path), "DATABASE_SERVER", new_db_server.strip())
            set_key(str(env_path), "DATABASE_NAME", new_db_name.strip())
            set_key(str(env_path), "DATABASE_USER", new_db_user.strip())
            set_key(str(env_path), "DATABASE_PASSWORD", new_db_password.strip())
            set_key(str(env_path), "DATABASE_PORT", new_db_port.strip())
            set_key(str(env_path), "DATABASE_DSN", "")
        else:
            set_key(str(env_path), "DATABASE_DSN", new_db_dsn.strip())
            set_key(str(env_path), "DATABASE_USER", new_db_user.strip())
            set_key(str(env_path), "DATABASE_PASSWORD", new_db_password.strip())
            set_key(str(env_path), "DATABASE_DRIVER", "")
            set_key(str(env_path), "DATABASE_SERVER", "")
            set_key(str(env_path), "DATABASE_NAME", "")
            set_key(str(env_path), "DATABASE_PORT", "")
        
        st.success("Configuration updated successfully.")
        updated_config = get_config()
        display_config_table(updated_config)
        
        if new_llm_model.strip():
            if test_model_connection(new_llm_model.strip()):
                st.success("Successfully connected to the LLM model.")
            else:
                st.error("Failed to connect to the LLM model. Please verify the model name and OpenAI configuration.")
    
    st.header(":test_tube: Test Database Connection")
    current_mode = get_config().get("CONNECTION_MODE", "MANUAL").strip().upper() or "MANUAL"
    if current_mode == "ODBC_DSN":
        st.info("Testing ODBC DSN connection")
    else:
        st.info("Testing Manual connection string")
    
    if st.button("Test DB Connection"):
        # Logging to terminal current working directory
        sys.path.insert(0, os.path.abspath(os.getcwd()))
        print("Current working directory:", os.getcwd())
        print("Python sys.path:")
        for path in sys.path:
            print("  ", path)
        try:
            sql_query = "SELECT @@version"
            connector = SQLConnector()
            # Get the result rows directly from execute_query().
            result = connector.execute_query(sql_query)
            # Retrieve column name from the cursor description if available.
            column_name = connector.cursor.description[0][0] if connector.cursor.description else 'db_test_connection'
            
            # Build a DataFrame if there is any result.
            if result:
                df = pd.DataFrame(result, columns=[column_name])
                df = df.astype(str)  # <-- Force all columns to string to avoid Arrow errors
            else:
                df = pd.DataFrame()
            
            connector.close_connection()
            st.success("Database connection successful.")
            st.write("Test Query Result:")
            st.dataframe(df)
        except Exception as e:
            st.error(f"Database connection test failed: {e}")
    
    st.write("Return to the **Chat** page to interact with your SQL Database Chatbot.")
    
    st.header("🔄 LLM Schema Cache Management")

    if st.button("Refresh Schema Map Cache"):
        schema_map = get_schema_map_tool()  # this repopulates the SCHEMA_CACHE
        st.success("✅ Schema cache has been refreshed from the database.")
        st.subheader("📦 Current Schema Map:")
        st.json(schema_map)

if __name__ == "__main__":
    main()
