# app/streamlit_app.py
"""
IMPORTANT: This is the main entry point for the Streamlit application.
st.set_page_config() MUST:
1. Be in this file only
2. Be the first Streamlit command
3. Never be in any other file

Common bug: Adding st.set_page_config() to other files or after other Streamlit commands 
will cause the error:
    StreamlitSetPageConfigMustBeFirstCommandError
"""

# Standard library imports
import streamlit as st
import logging
import logging.config
from pathlib import Path
import sys
import os
from dotenv import load_dotenv
from streamlit_option_menu import option_menu
import logging.handlers
from datetime import datetime

# Add project root to Python path if not already there
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Backend imports
from backend.system import get_system_status, get_status_emoji, test_db_connection, LOG_CONFIG
from backend.system import test_llm_connection
from backend.db_tools import get_databases

# App imports
from app import (
    chat,
    chat_react,
    configuration,
    audit_log,
    home,
    tools
)

# Configure logging
import logging.handlers

# Create logs directory if it doesn't exist
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# Create a daily rotating file handler
log_file = log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.log"
file_handler = logging.handlers.TimedRotatingFileHandler(
    filename=log_file,
    when='midnight',
    interval=1,
    backupCount=30,  # Keep logs for 30 days
    encoding='utf-8'
)
file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(file_handler)

# Add StreamlitHandler for UI display
class StreamlitHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.log_buffer = []

    def emit(self, record):
        log_entry = self.format(record)
        if 'log_messages' not in st.session_state:
            st.session_state.log_messages = []
        st.session_state.log_messages.append(log_entry)

streamlit_handler = StreamlitHandler()
streamlit_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))
root_logger.addHandler(streamlit_handler)

logger = logging.getLogger(__name__)

# Must be the first Streamlit command
st.set_page_config(
    page_title="SQL Chat Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load environment variables from .env file
load_dotenv()

# Get debug mode from environment variable
debug_mode = os.getenv("DEBUG", "").lower() == "true"

# Initialize session state
if 'db_connected' not in st.session_state:
    st.session_state.db_connected = False
if 'llm_connected' not in st.session_state:
    st.session_state.llm_connected = False

def show_system_status():
    """Show system status in sidebar."""
    st.sidebar.header("System Status")
    
    # Get status from backend
    db_status, llm_status = get_system_status()
    
    # Display status
    st.sidebar.markdown(f"{get_status_emoji(db_status)} **Database**")
    st.sidebar.markdown(f"{get_status_emoji(llm_status)} **LLM**")

def main():
    """Main application interface."""
    
    # Sidebar navigation using option_menu
    with st.sidebar:
        page = option_menu(
            menu_title=None,
            options=["Home", "Chat", "Advanced Chat", "Configuration", "Audit Log", "Tools"],
            icons=["house-fill", "chat-fill", "search", "gear-fill", "card-list", "wrench"],
            menu_icon="cast",
            default_index=0,
        )
        
        # Show system status
        show_system_status()
        
        # Show version info
        st.markdown("---")
        st.caption("SQL Chat Assistant v1.0.0")
    
    # Page Router
    if page == "Home":
        home.main()
    elif page == "Chat":
        chat.main()
    elif page == "Advanced Chat":
        chat_react.main()
    elif page == "Configuration":
        configuration.main()
    elif page == "Audit Log":
        audit_log.main()
    elif page == "Tools":
        tools.main()

if __name__ == "__main__":
    main()
