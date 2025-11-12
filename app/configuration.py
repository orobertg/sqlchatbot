# app/configuration.py

"""
Configuration Interface Module
Handles configuration settings and testing
"""

import os
import streamlit as st
from dotenv import load_dotenv
from pathlib import Path
import json
from typing import Dict, Any, List, Optional, Tuple
import logging
from backend.system import (
    test_db_connection,
    test_llm_connection,
    DB_CONFIG,
    LLM_CONFIG
)
from backend.llm_engine import (
    list_local_models
)
from backend.db_tools import get_databases, clear_schema_cache
import requests

# Get the project root directory and load .env file
PROJECT_ROOT = Path(__file__).parent.parent
ENV_PATH = PROJECT_ROOT / '.env'
load_dotenv(ENV_PATH)

# Configure logging
logger = logging.getLogger(__name__)

"""
Configuration Page Module
------------------------
This module handles the UI/display logic for the configuration page.
IMPORTANT: This module should NOT contain any direct database or LLM operations.

All backend operations should be imported from:
- backend.llm_engine (for LLM operations)
- backend.db_tools (for database operations)

Required backend functions:
- test_llm_connection(): -> Tuple[bool, str]
- list_local_models(): -> List[str]
- get_llm_instance(): -> LocalLLM
- set_llm_instance(model: str): -> None
- test_db_connection(): -> Tuple[bool, str]

Do not implement these operations here - import them from backend modules.
"""

import os,sys
from pathlib import Path
from dotenv import load_dotenv, set_key, dotenv_values
import httpx
import time

# Internal imports
from backend.llm_engine import (
    set_llm_instance, 
    list_local_models, 
    test_llm_connection
)
from backend.system import test_db_connection


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
    config = dotenv_values(str(ENV_PATH))
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
    Retrieve available model names from the local endpoint with caching.
    """
    if 'available_models' in st.session_state:
        return st.session_state.available_models
        
    try:
        base_url = os.getenv("OPENAI_API_BASE", "http://localhost:11434/").rstrip("/")
        if base_url.endswith("/v1"):
            base_url = base_url[:-3].rstrip("/")
        url = f"{base_url}/api/tags" 
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        models = [m["name"] for m in data.get("models", [])]
        st.session_state.available_models = models
        return models
    except Exception as e:
        st.error(f"Error retrieving available models: {e}")
        return []

def test_model_connection(model_name: str) -> Tuple[bool, str]:
    """
    Test connection to the specified model.
    Returns a tuple of (success, message).
    """
    try:
        # First set the model
        set_llm_instance(model_name)
        
        # Then test the connection
        success, message = test_llm_connection()
        return success, message
        
    except Exception as e:
        logger.error(f"LLM Connection test failed: {e}")
        return False, f"Connection test failed: {str(e)}"

def test_database_connection():
    """Test the database connection"""
    try:
        connector = SQLConnector()
        results, error = connector.execute_query("SELECT @@version")
        if error:
            return False, f"Database connection test failed: {error}"
        connector.close()
        return True, "Database connection test successful!"
    except Exception as e:
        return False, f"Database connection test failed: {str(e)}"

def get_raw_model_info():
    """Get raw model information from Ollama API"""
    try:
        base_url = os.getenv("OPENAI_API_BASE", "http://localhost:11434/").rstrip("/")
        if base_url.endswith("/v1"):
            base_url = base_url[:-3].rstrip("/")
        url = f"{base_url}/api/tags"
        
        import requests
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}

# Setup logging to capture all messages
class StreamlitHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.log_buffer = []

    def emit(self, record):
        log_entry = self.format(record)
        if 'log_messages' not in st.session_state:
            st.session_state.log_messages = []
        st.session_state.log_messages.append(log_entry)

def setup_logging():
    if 'logging_setup' not in st.session_state:
        handler = StreamlitHandler()
        formatter = logging.Formatter('%(levelname)s:%(name)s:%(message)s')
        handler.setFormatter(formatter)
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        st.session_state.logging_setup = True

def save_env_variables(updates):
    """Save variables to .env file without clearing existing values."""
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        # Read existing contents
        lines = env_path.read_text().splitlines()
        updated_lines = []
        updated_vars = set()
        
        # Update existing lines
        for line in lines:
            if line.strip() and not line.strip().startswith('#'):
                key = line.split('=')[0].strip()
                if key in updates:
                    updated_lines.append(f"{key}='{updates[key]}'")
                    updated_vars.add(key)
                else:
                    updated_lines.append(line)
            else:
                updated_lines.append(line)
        
        # Add any new variables
        for key, value in updates.items():
            if key not in updated_vars:
                updated_lines.append(f"{key}='{value}'")
        
        # Write back to file
        env_path.write_text('\n'.join(updated_lines))
        
        # Reload environment
        load_dotenv(override=True)

def get_status_emoji(status: bool) -> str:
    """Get the appropriate status emoji indicator."""
    return "🟢" if status else "🔴"

def get_env_status(env_var: str) -> bool:
    """Check if an environment variable is set and not empty."""
    return bool(os.getenv(env_var, ""))

def show_status_overview():
    """Show overall status of system components."""
    col1, col2 = st.columns(2)
    
    with col1:
        db_status, db_message = test_db_connection()
        st.markdown(f"**Database Status:** {'🟢' if db_status else '🔴'}")
        
    with col2:
        llm_status, llm_message = test_llm_connection()
        st.markdown(f"**LLM Status:** {'🟢' if llm_status else '🔴'}")

def update_status_displays():
    """Update all status displays (top chart and sidebar)."""
    # Force a rerun of the main app to update sidebar
    st.rerun()

def show_db_config():
    """Show database configuration section."""
    st.header("🗄️ Database Configuration")
    
    # Initialize session state for DB test status if not exists
    if "db_test_status" not in st.session_state:
        st.session_state.db_test_status = None
    
    # Display persistent status message if exists
    if st.session_state.db_test_status:
        if st.session_state.db_test_status["success"]:
            st.success(st.session_state.db_test_status["message"])
        else:
            st.error(st.session_state.db_test_status["message"])
    
    current_mode = os.getenv("CONNECTION_MODE", "").strip()
    
    # Create main container
    main_container = st.container()
    
    with main_container:
        conn_tab1, conn_tab2 = st.tabs([
            "🔌 Connection String", 
            "🔗 ODBC DSN"
        ])
        
        # Connection String tab
        with conn_tab1:
            if current_mode != "Connection String":
                st.warning("Using DSN configuration. Save connection string settings to switch modes.")
            
            st.markdown("##### Connection Settings")
            col1, *_ = st.columns([2, 4])
            with col1:
                new_driver = st.text_input("Driver", 
                    value=os.getenv("DATABASE_DRIVER", "SQL Server"),
                    help="Example: {ODBC Driver 17 for SQL Server}"
                )
                new_server = st.text_input("Server", value=os.getenv("DATABASE_SERVER", ""))
                new_database = st.text_input("Database", value=os.getenv("DATABASE_NAME", ""))
                new_username = st.text_input("Username", value=os.getenv("DATABASE_USER", ""))
                new_password = st.text_input("Password", type="password", value=os.getenv("DATABASE_PASSWORD", ""))
            
            st.markdown("---")
            
            col1, *_ = st.columns([1, 3])
            with col1:
                if st.button("💾 Save", key="db_conn_string_save_btn", use_container_width=True):
                    # Validate required fields
                    missing_fields = []
                    if not new_driver.strip():
                        missing_fields.append("Driver")
                    if not new_server.strip():
                        missing_fields.append("Server")
                    if not new_database.strip():
                        missing_fields.append("Database")
                    if not new_username.strip():
                        missing_fields.append("Username")
                    if not new_password.strip():
                        missing_fields.append("Password")
                    
                    if missing_fields:
                        st.error(f"Please fill in all required fields: {', '.join(missing_fields)}")
                        return
                    
                    # All fields are filled, proceed with save
                    conn_string = f"DRIVER={{{new_driver.strip()}}};SERVER={new_server.strip()};DATABASE={new_database.strip()};UID={new_username.strip()};PWD={new_password.strip()}"
                    env_vars = {
                        "DATABASE_CONNECTION_STRING": conn_string,
                        "DATABASE_DRIVER": new_driver.strip(),
                        "DATABASE_SERVER": new_server.strip(),
                        "DATABASE_NAME": new_database.strip(),
                        "DATABASE_USER": new_username.strip(),
                        "DATABASE_PASSWORD": new_password.strip(),
                        "CONNECTION_MODE": "Connection String"
                    }
                    update_env_file(lines=open(".env").readlines(), env_vars=env_vars)
                    st.success("Connection string configuration saved")
                    time.sleep(0.5)
                    st.rerun()
                
                st.markdown("")
                
                if st.button("🔄 Test", 
                            key="db_conn_string_test_btn",
                            use_container_width=True):
                    # Validate configuration exists
                    missing_fields = []
                    if not os.getenv("DATABASE_DRIVER", "").strip():
                        missing_fields.append("Driver")
                    if not os.getenv("DATABASE_SERVER", "").strip():
                        missing_fields.append("Server")
                    if not os.getenv("DATABASE_NAME", "").strip():
                        missing_fields.append("Database")
                    if not os.getenv("DATABASE_USER", "").strip():
                        missing_fields.append("Username")
                    if not os.getenv("DATABASE_PASSWORD", "").strip():
                        missing_fields.append("Password")
                    
                    if missing_fields:
                        st.session_state.db_test_status = {
                            "success": False,
                            "message": f"❌ Missing required fields: {', '.join(missing_fields)}. Please save your configuration first."
                        }
                        st.rerun()
                        return
                    
                    with st.spinner("Testing connection string configuration..."):
                        success, message = test_db_connection()
                        st.session_state.db_test_status = {
                            "success": success,
                            "message": f"{'✅' if success else '❌'} {message}"
                        }
                        st.rerun()
        
        # DSN tab
        with conn_tab2:
            if current_mode != "DSN":
                st.warning("Using connection string configuration. Save DSN settings to switch modes.")
            
            st.markdown("##### DSN Settings")
            col1, *_ = st.columns([2, 4])
            with col1:
                new_dsn = st.text_input("DSN Name", value=os.getenv("DATABASE_DSN", ""))
                new_username = st.text_input("SQL Server Login", 
                                           value=os.getenv("DATABASE_USER", ""),
                                           key="dsn_username")
                new_password = st.text_input("SQL Server Password", 
                                           type="password",
                                           value=os.getenv("DATABASE_PASSWORD", ""),
                                           key="dsn_password")
            
            st.markdown("---")
            
            col1, *_ = st.columns([1, 3])
            with col1:
                if st.button("💾 Save", key="db_dsn_save_btn", use_container_width=True):
                    # Validate required fields
                    missing_fields = []
                    if not new_dsn.strip():
                        missing_fields.append("DSN Name")
                    if not new_username.strip():
                        missing_fields.append("SQL Server Login")
                    if not new_password.strip():
                        missing_fields.append("SQL Server Password")
                    
                    if missing_fields:
                        st.error(f"Please fill in all required fields: {', '.join(missing_fields)}")
                        return
                    
                    # All fields are filled, proceed with save
                    env_vars = {
                        "DATABASE_DSN": new_dsn.strip(),
                        "DATABASE_USER": new_username.strip(),
                        "DATABASE_PASSWORD": new_password.strip(),
                        "CONNECTION_MODE": "DSN"
                    }
                    update_env_file(lines=open(".env").readlines(), env_vars=env_vars)
                    st.success("DSN configuration saved")
                    time.sleep(0.5)
                    st.rerun()
                
                st.markdown("")
                
                if st.button("🔄 Test", 
                            key="db_dsn_test_btn",
                            use_container_width=True):
                    # Validate fields before testing
                    missing_fields = []
                    if not os.getenv("DATABASE_DSN", "").strip():
                        missing_fields.append("DSN Name")
                    if not os.getenv("DATABASE_USER", "").strip():
                        missing_fields.append("SQL Server Login")
                    if not os.getenv("DATABASE_PASSWORD", "").strip():
                        missing_fields.append("SQL Server Password")
                    
                    if missing_fields:
                        st.session_state.db_test_status = {
                            "success": False,
                            "message": f"❌ Missing required fields: {', '.join(missing_fields)}. Please save your configuration first."
                        }
                        st.rerun()
                        return
                    
                    with st.spinner("Testing DSN configuration..."):
                        success, message = test_db_connection()
                        st.session_state.db_test_status = {
                            "success": success,
                            "message": f"{'✅' if success else '❌'} {message}"
                        }
                        st.rerun()

def show_audit_config():
    """Show audit configuration section."""
    st.header("📝 Audit Configuration")
    st.info("Audit configuration settings coming soon...")

def show_advanced_config():
    """Show advanced configuration section."""
    st.header("⚙️ Advanced Configuration")
    st.info("Advanced configuration settings coming soon...")

def show_chat_config():
    """Show chat configuration section."""
    st.header("Chat Configuration")
    st.info("Chat settings configuration coming soon...")

def show_security_config():
    """Show security configuration section."""
    st.header("Security Configuration")
    st.info("Security settings configuration coming soon...")

def show_system_config():
    """Show system configuration section."""
    st.header("System Configuration")
    st.info("System settings configuration coming soon...")

def main():
    """Display configuration settings page with tabs."""
    st.title("⚙️ Configuration")
    
    # Create tabs for different configuration sections
    tab1, tab2, tab3, tab4 = st.tabs([
        "🤖 LLM", 
        "🗄️ Database", 
        "📝 Audit", 
        "⚙️ Advanced"
    ])
    
    with tab1:
        show_llm_config()
        
    with tab2:
        show_db_config()
        
    with tab3:
        show_audit_config()
        
    with tab4:
        show_advanced_config()

def update_env_file(lines, env_vars):
    """Update environment variables in .env file."""
    # Create a set of existing variable names
    existing_vars = set()
    new_lines = []
    
    # Process existing lines
    for line in lines:
        line = line.strip()
        if line and not line.startswith('#'):
            var_name = line.split('=')[0].strip()
            existing_vars.add(var_name)
            
            # If this variable is being updated, use new value
            if var_name in env_vars:
                new_lines.append(f"{var_name}='{env_vars[var_name]}'")
            else:
                new_lines.append(line)
    
    # Add any new variables that didn't exist before
    for var_name, value in env_vars.items():
        if var_name not in existing_vars:
            new_lines.append(f"{var_name}='{value}'")
    
    # Write back to file with each variable on a new line
    with open(".env", "w") as f:
        for line in new_lines:
            f.write(f"{line}\n")  # Add newline after each variable

def get_current_env_vars():
    """Read current environment variables from .env file."""
    try:
        # Force reload of .env file
        load_dotenv(override=True)
        
        # Read directly from .env file
        env_path = Path(__file__).parent.parent / '.env'
        if env_path.exists():
            config = dotenv_values(str(env_path))
            return config
        return {}
    except Exception as e:
        logger.error(f"Error reading .env file: {e}")
        return {}

def show_llm_config():
    """Show LLM configuration section."""
    st.header("🤖 LLM Configuration")
    
    # Initialize session states
    if "llm_test_status" not in st.session_state:
        st.session_state.llm_test_status = None
    
    # Get current environment variables
    current_env = get_current_env_vars()
    
    # Initialize session state with current values from .env
    if "current_llm" not in st.session_state:
        st.session_state.current_llm = {
            "model": current_env.get("LLM_MODEL", "Not set"),
            "base_url": current_env.get("OPENAI_API_BASE", "http://localhost:11434")
        }
    
    # Display current LLM model from .env file
    current_model = current_env.get("LLM_MODEL", "Not set")
    st.markdown(f"**Current Model:** `{current_model}`")
    
    # Display persistent status message if exists
    if st.session_state.llm_test_status:
        if st.session_state.llm_test_status["success"]:
            st.success(st.session_state.llm_test_status["message"])
        else:
            st.error(st.session_state.llm_test_status["message"])
    
    # Create a container for the main content
    main_container = st.container()
    
    with main_container:
        st.markdown("##### Model Settings")
        
        # Get available models with caching
        available_models = get_available_models()
        
        if not available_models:
            st.warning("No local models found. Please ensure Ollama is running and has models installed.")
            return
        
        col1, *_ = st.columns([2, 4])
        with col1:
            # Model selection - use current model from .env as default
            try:
                default_index = available_models.index(current_model) if current_model in available_models else 0
            except ValueError:
                default_index = 0
                
            selected_model = st.selectbox(
                "Select Model",
                available_models,
                index=default_index
            )
            
            # Base URL configuration
            base_url = st.text_input(
                "Ollama Base URL",
                value=os.getenv("OPENAI_API_BASE", "http://localhost:11434"),
                help="URL where Ollama is running"
            )
        
        # Add separator before buttons
        st.markdown("---")
        
        # Action buttons in a single column, left-justified
        col1, *_ = st.columns([1, 3])
        with col1:
            if st.button("Test Connection"):
                with st.spinner("Testing connection..."):
                    success, message = test_model_connection(selected_model)
                    st.session_state.llm_test_status = {
                        "success": success,
                        "message": message
                    }
                st.experimental_rerun()

def show_current_llm_config():
    """Display current LLM configuration."""
    st.markdown("**Current LLM Configuration**")
    st.markdown(f"""
    - **Model**: {os.getenv("LLM_MODEL", "Not set")}
    - **Base URL**: {os.getenv("OPENAI_API_BASE", "Not set")}
    """)

if __name__ == "__main__":
    main()
