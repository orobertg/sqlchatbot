import streamlit as st
from backend.db_tools import get_schema_map, get_schema_map_formatted, clear_schema_cache
import json
import logging
from pathlib import Path
from datetime import datetime
import os

def setup_log_directory():
    """Setup log directory structure."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    return log_dir

def get_log_files():
    """Get list of available log files."""
    log_dir = setup_log_directory()
    log_files = sorted([f for f in log_dir.glob("*.log")], reverse=True)
    return log_files

def read_log_file(file_path):
    """Read log file content."""
    try:
        with open(file_path, 'r') as f:
            return f.readlines()
    except Exception as e:
        st.error(f"Error reading log file: {str(e)}")
        return []

def filter_logs(logs, level=None, search_text=None):
    """Filter logs based on level and search text."""
    filtered_logs = logs
    
    if level:
        filtered_logs = [log for log in filtered_logs if f"[{level}]" in log]
    
    if search_text:
        filtered_logs = [log for log in filtered_logs if search_text.lower() in log.lower()]
    
    return filtered_logs

def clear_log_file(file_path):
    """Clear contents of a specific log file."""
    try:
        # Ensure the file exists
        if not file_path.exists():
            st.error(f"Log file does not exist: {file_path}")
            return False
            
        # Get the root logger
        root_logger = logging.getLogger()
        
        # Find and close the file handler for this file
        for handler in root_logger.handlers[:]:
            if isinstance(handler, logging.handlers.TimedRotatingFileHandler):
                if handler.baseFilename == str(file_path.absolute()):
                    handler.close()
                    root_logger.removeHandler(handler)
                    break
        
        # Now clear the file contents
        file_path.write_text('')
        
        # Recreate the file handler
        new_handler = logging.handlers.TimedRotatingFileHandler(
            filename=file_path,
            when='midnight',
            interval=1,
            backupCount=30,
            encoding='utf-8'
        )
        new_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))
        root_logger.addHandler(new_handler)
        
        logger.info(f"Successfully cleared log file: {file_path}")
        return True
    except Exception as e:
        logger.error(f"Error clearing log file {file_path}: {str(e)}")
        st.error(f"Error clearing log file: {str(e)}")
        return False

def clear_all_logs():
    """Clear all log files."""
    log_dir = setup_log_directory()
    try:
        # Get all log files
        log_files = list(log_dir.glob("*.log"))
        if not log_files:
            st.warning("No log files found to clear")
            return True
            
        # Get the root logger
        root_logger = logging.getLogger()
        
        # Remove all TimedRotatingFileHandlers
        for handler in root_logger.handlers[:]:
            if isinstance(handler, logging.handlers.TimedRotatingFileHandler):
                handler.close()
                root_logger.removeHandler(handler)
        
        # Clear each file
        for log_file in log_files:
            try:
                log_file.write_text('')
                logger.info(f"Successfully cleared log file: {log_file}")
            except Exception as e:
                logger.error(f"Error clearing log file {log_file}: {str(e)}")
                st.error(f"Error clearing log file {log_file.name}: {str(e)}")
                return False
        
        # Recreate the file handler for the current day's log
        current_log = log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.log"
        new_handler = logging.handlers.TimedRotatingFileHandler(
            filename=current_log,
            when='midnight',
            interval=1,
            backupCount=30,
            encoding='utf-8'
        )
        new_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))
        root_logger.addHandler(new_handler)
                
        return True
    except Exception as e:
        logger.error(f"Error in clear_all_logs: {str(e)}")
        st.error(f"Error clearing all logs: {str(e)}")
        return False

def show_debug_logs():
    """Show debug logs with filtering capabilities."""
    st.header("Debug Logs")
    
    # Setup log directory
    log_dir = setup_log_directory()
    
    # Get available log files
    log_files = get_log_files()
    
    if not log_files:
        st.info("No log files available")
        return
    
    # Create three columns for the interface
    col1, col2, col3 = st.columns([1, 3, 1])
    
    with col1:
        st.subheader("Log Files")
        # Show log files with dates
        selected_file = None
        for log_file in log_files:
            date_str = log_file.stem  # Assuming filename is the date
            if st.button(f"📄 {date_str}", key=str(log_file)):
                selected_file = log_file
    
    with col2:
        if selected_file:
            st.subheader(f"Log Contents: {selected_file.name}")
            
            # Filter options
            filter_col1, filter_col2 = st.columns(2)
            with filter_col1:
                level = st.selectbox(
                    "Filter by Level",
                    ["All", "INFO", "WARNING", "ERROR", "DEBUG"],
                    key="log_level"
                )
            
            with filter_col2:
                search_text = st.text_input("Search in logs", key="log_search")
            
            # Read and filter logs
            logs = read_log_file(selected_file)
            if logs:
                filtered_logs = filter_logs(
                    logs,
                    level=None if level == "All" else level,
                    search_text=search_text
                )
                
                # Display logs in a scrollable container
                with st.container():
                    for log in filtered_logs:
                        st.text(log.strip())
                
                # Show log count
                st.caption(f"Showing {len(filtered_logs)} of {len(logs)} log entries")
            else:
                st.info("No logs found in this file")
        else:
            st.info("Select a log file to view its contents")
    
    with col3:
        st.subheader("Log Management")
        
        # Clear selected log file
        if selected_file:
            if st.button("🗑️ Clear Selected Log", key="clear_selected"):
                if clear_log_file(selected_file):
                    st.success(f"Cleared log file: {selected_file.name}")
                    st.experimental_rerun()
        
        # Clear all logs
        if st.button("🗑️ Clear All Logs", key="clear_all"):
            if st.checkbox("I confirm I want to delete all logs", key="confirm_clear_all"):
                if clear_all_logs():
                    st.success("All logs have been cleared")
                    st.experimental_rerun()
            else:
                st.warning("Please confirm before clearing all logs")

def show_schema_viewer():
    """Show schema viewer."""
    st.header("Schema Viewer")
    
    # Add a refresh button
    if st.button("Refresh Schema"):
        clear_schema_cache()
        st.experimental_rerun()
    
    # Get schema map
    schema_map = get_schema_map()
    
    if not schema_map:
        st.error("No schema information available")
        return
    
    # Show full JSON schema map
    with st.expander("Full Schema Map (JSON)"):
        st.json(schema_map)
    
    # Show formatted schema view
    st.subheader("Formatted Schema View")
    
    # Create columns for schemas
    cols = st.columns(min(3, len(schema_map)))
    
    # Display schemas and their tables
    for i, (schema_name, schema_info) in enumerate(schema_map.items()):
        with cols[i % 3]:
            st.markdown(f"### {schema_name}")
            
            for table_name, table_info in schema_info.get('tables', {}).items():
                with st.expander(f"📊 {table_name}"):
                    # Show columns
                    st.markdown("#### Columns")
                    for col_name, col_info in table_info.get('columns', {}).items():
                        # Add visual indicators for primary and foreign keys
                        indicators = []
                        if col_name in table_info.get('primary_keys', []):
                            indicators.append("🔑")
                        if any(fk['column'] == col_name for fk in table_info.get('foreign_keys', [])):
                            indicators.append("🔗")
                        
                        st.markdown(f"- {col_name} ({col_info['type']}) {' '.join(indicators)}")
                    
                    # Show primary keys
                    if table_info.get('primary_keys'):
                        st.markdown("#### Primary Keys")
                        for pk in table_info['primary_keys']:
                            st.markdown(f"- {pk}")
                    
                    # Show foreign keys
                    if table_info.get('foreign_keys'):
                        st.markdown("#### Foreign Keys")
                        for fk in table_info['foreign_keys']:
                            st.markdown(f"- {fk['column']} → {fk['references']}")

def main():
    """Main function for the Tools page."""
    st.title("Tools")
    
    # Add tabs for different tools
    tab1, tab2 = st.tabs(["Schema Viewer", "Debug Logs"])
    
    with tab1:
        show_schema_viewer()
    
    with tab2:
        show_debug_logs()

if __name__ == "__main__":
    main() 