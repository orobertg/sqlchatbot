# app/home.py

import streamlit as st

def main():
    st.title(":robot_face: SQL Chatbot")
    
    st.header(":page_with_curl: Overview")
    st.write("""
        The SQL Database Chatbot enables you to interact with your MS SQL Database using natural language queries.
        It leverages a locally hosted LLM to translate natural language descriptions into SQL queries.
    """)
    
    st.header(":bookmark_tabs: Quick Start")
    st.markdown("""
    1. Go to the **Configuration** page to set up your database and LLM settings
    2. Navigate to the **Chat** page to start interacting with your database
    3. Use natural language to describe what data you want to query
    """)
    
    st.header(":scroll: Key Features")
    st.markdown("""
    - **Natural Language to SQL**: Convert plain English to SQL queries
    - **Schema-Aware**: Automatically understands your database structure
    - **Safe Execution**: Reviews queries before execution
    - **Advanced Mode**: Additional features for complex queries
    """)

if __name__ == "__main__":
    main()
