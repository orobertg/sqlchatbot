# app/streamlit_app.py

import os
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from pathlib import Path
from backend.audit_logger import init_audit_log
from backend.audit_logger import log_query_event
import time

# Load environment
load_dotenv(dotenv_path=Path('.') / '.env', override=True)

# Local imports
from config.database_config import DATABASE_CONFIG
from backend.tools import get_schema_map_tool
from backend.controller import process_user_prompt, is_destructive
from backend.sql_connector import validate_db_connection

# Initialize audit log on app startup
init_audit_log()

# --- Sidebar Navigation ---
with st.sidebar:
    from streamlit_option_menu import option_menu
    page = option_menu(
        menu_title=None,
        options=["Home","Config","Chat","Tools","Audit Log"],  
        icons=["house-fill","gear-fill","chat-fill","wrench","card-list"],
        menu_icon="cast",
        default_index=0,
    )

# --- Page Router ---
if page == "Home":
    from app import info
    info.main()

elif page == "Config":
    from app import configuration
    configuration.main()

elif page == "Chat":
    from app import chat
    chat.main()

elif page == "Tools":
    from app import db_tools
    db_tools.main()

elif page == "Audit Log":
    from app import audit_log
    audit_log.main()
