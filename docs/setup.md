# SQL Chatbot Setup Guide

## Prerequisites
- Python 3.8+
- SQL Server with ODBC Driver
- Ollama or compatible LLM service
- Git (for version control)

## Installation

### 1. Clone the Repository
git clone https://github.com/yourusername/sqlchatbot.git
cd sqlchatbot

### 2. Create Virtual Environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

### 3. Install Dependencies
pip install -r requirements.txt

### 4. Configure Environment Variables
Create a .env file in the root directory:

DB_DRIVER={ODBC Driver 17 for SQL Server}
DB_SERVER=localhost,1433
DB_DATABASE=YourDatabase
DB_UID=YourUsername
DB_PWD=YourPassword
OPENAI_API_BASE=http://localhost:11434/v1
LLM_MODEL=qwen2.5-coder:7b

### 5. Start the Application
streamlit run app/streamlit_app.py

## Configuration

### Database Setup
1. Install SQL Server
2. Install ODBC Driver
3. Create database
4. Configure firewall rules
5. Test connection

### LLM Setup
1. Install Ollama
2. Pull required models
3. Start Ollama service
4. Test LLM connection

### Troubleshooting Installation

#### Database Connection Issues
- Verify SQL Server is running
- Check firewall settings
- Test connection string
- Verify ODBC driver installation
- Check user permissions

#### LLM Service Issues
- Verify Ollama is running
- Check API endpoint
- Test model availability
- Verify network connectivity
- Monitor resource usage

## Updating the Application

### Code Updates
1. Pull latest changes
2. Update dependencies
3. Check environment variables
4. Restart application

### Database Updates
1. Backup existing data
2. Apply schema changes
3. Update connection settings
4. Test functionality

### LLM Updates
1. Update Ollama
2. Pull new models
3. Update configuration
4. Test prompts 