# SQL Chatbot Architecture Documentation

## System Overview
The SQL Chatbot is a Streamlit-based application that provides a natural language interface to SQL databases using LLM technology. Users can ask questions in plain English, which are then converted to SQL queries and executed against the database.

## Critical Code Considerations

### Streamlit Configuration
⚠️ **CRITICAL**: st.set_page_config() must only be in app/streamlit_app.py and must be the first Streamlit command.

Example in app/streamlit_app.py ONLY:
st.set_page_config(
    page_title="SQL Chatbot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

### System Architecture Diagram
graph TD
    A[streamlit_app.py] --> B[configuration.py]
    A --> C[chat.py]
    B --> D[sql_connector.py]
    B --> E[llm_engine.py]
    C --> D
    C --> E

## Core Components

### 1. Main Application (app/streamlit_app.py)
- Entry point for the Streamlit application
- Handles page configuration and routing
- Manages session state initialization
- Controls sidebar navigation

### 2. Configuration (app/configuration.py)
- Manages system settings
- Handles logging setup
- Displays system status
- Tests connections

### 3. Chat Interface (app/chat.py)
- Implements chat UI
- Handles user interactions
- Manages chat history

### 4. Database Connector (backend/sql_connector.py)
- Manages database connections
- Executes SQL queries
- Handles query results

### 5. LLM Engine (backend/llm_engine.py)
- Manages LLM service connections
- Handles prompt engineering
- Processes LLM responses

## Data Flow
1. User Input → Chat Interface
2. Chat Interface → LLM Engine
3. LLM Engine → SQL Generation
4. SQL → Database Connector
5. Results → Chat Interface
6. Display → User

## Session State Management
The application uses Streamlit's session state to maintain application state across reruns:

- log_messages: System logs
- db_connected: Database connection status
- llm_connected: LLM service status
- chat_history: User chat history

## Logging System
Custom StreamlitHandler implementation for integrated logging:

class StreamlitHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.log_buffer = []

## Environment Configuration
Required environment variables:

DB_DRIVER=SQL Server driver
DB_SERVER=Database server address
DB_DATABASE=Database name
DB_UID=Database username
DB_PWD=Database password
OPENAI_API_BASE=LLM API endpoint
LLM_MODEL=LLM model name