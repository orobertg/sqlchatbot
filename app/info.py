import streamlit as st
import subprocess
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables to show current configuration info.
load_dotenv()

def list_local_models():
    """
    List available models using the local endpoint.
    Returns a list of model names or an error message.
    """
    try:
        base_url = os.getenv("OPENAI_API_BASE", "http://localhost:11434/").rstrip("/")
        # Ensure no trailing /v1 is present.
        if base_url.endswith("/v1"):
            base_url = base_url[:-3].rstrip("/")
        url = f"{base_url}/api/tags"
        response = subprocess.run(["curl", "-s", url], capture_output=True, text=True)
        data = response.stdout
        # For simplicity, let's assume the JSON structure is like:
        # { "models": [ {"name": "model1"}, {"name": "model2"}, ... ] }
        import json
        data_dict = json.loads(data)
        models = [m["name"] for m in data_dict.get("models", [])]
        return models
    except Exception as e:
        st.error(f"Error retrieving available models: {e}")
        return []

def main():
    st.title(":robot_face: SQL Database Chatbot")
    
    st.header(":page_with_curl: Overview")
    st.write("""
        The SQL Database Chatbot enables you to interact with your MS SQL Database using natural language queries.
        It leverages a locally hosted LLM (such as an OpenLlama model via OpenAI’s ChatCompletion API) to translate natural
        language descriptions into SQL queries.
    """)
    
    st.header(":bookmark_tabs: Usage Instructions")
    st.markdown("""
    **How It Works:**
    1. **Input Your Query:**  
       Provide a natural language description of an SQL query, for example:  
       *"Show me the total sales for last quarter with a status of complete."*
    2. **SQL Generation:**  
       The system uses an LLM to generate the corresponding SQL command.
    3. **Review & Execution:**  
       You can review the generated SQL and then choose to execute it.
    """)
    st.write("Use the sidebar to navigate to the **Configuration** page for updating settings, or to the **Chat** page to interact with the SQL Database Chatbot.")
    
    st.header(":scroll: Features")
    st.markdown("""
    **LLM features:**
    1. **LLM Caching**  
      For databases with multiple schemas, the LLM caches the list of schemas. 
      This allows for reuse of things it knows alread to stay in memory without fetching them again.
    2. **LLM Data Classes**  
       Data Classes set a definition for expected SQL query INPUTs and OUTPUTs to the database.
      This refines the SQL querying to send and receive the right values, lowering LLM haulicination effects.
    3. **LLM Tool Access**  
       A specific set of Tools are accessible to the LLM to run when working with the database.
       These tools are automatically chosen based on the decisions by the LLM which you can review.
       Some LLMs are better than others at doing Tool handling decisions, play with them to find a good fit.
    """)
    
    st.header(":triangular_ruler: Requirements")
    st.markdown("""
    **Essential Requirements:**
    
    - **LLM and API Endpoint:**  
      A local LLM model (for example, we recommend one of the models available via OLLAMA hosted on your local endpoint) must be available.  
      Please ensure the OPENAI_API_BASE and OPENAI_API_KEY are configured correctly in the settings.
    
    - **MS SQL Server:**  
      The target MS SQL Server must be accessible over the network (remote connections enabled).  
      It should have a SQL Login account with the necessary read-write permissions for the target database,  
      as specified in the Configuration page.
      
    - **Configuration Settings:**  
      Verify that your .env file and Configuration page have the correct settings for the SQL Server connection
      (including server, database, user, password, and either DSN or manual connection fields).
    
    - **Network Requirements:**  
      The server should allow remote connections, and the necessary ports (typically 1433) must be open.
    """)
    
    st.header(":space_invader: Available LLM Models")
    models = list_local_models()
    if models:
        st.code("\n".join(models), language="bash")
    else:
        st.warning("No available models could be retrieved.")

if __name__ == "__main__":
    main()
