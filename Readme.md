# 🧠 SQL Chatbot – Natural Language to SQL, Powered by Local LLMs

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Streamlit](https://img.shields.io/badge/streamlit-1.25%2B-brightgreen)
![License](https://img.shields.io/badge/license-Apache%202.0-yellowgreen)
![Docker](https://img.shields.io/badge/docker-supported-blue)
![Chatbot](https://img.shields.io/badge/chatbot-LLM%20SQL%20Assistant-purple)

A modular, schema-aware chatbot that connects to your SQL Server database and turns natural language into executable SQL queries.

Built with:
- ✅ Streamlit for UI
- ✅ Ollama / Local LLMs (OpenAI Compatible)
- ✅ Microsoft SQL Server + PyODBC
- ✅ SQLite-based Non-Blocking Audit Logging
- ✅ Optional OpenTelemetry Observability

---

## 📂 Folder Structure

```bash
/sqlchatbot/
├── app/
│   ├── audit_log.py
│   ├── chat.py
│   ├── configuration.py
│   ├── db_tools.py
│   ├── info.py
│   ├── streamlit_app.py
├── backend/
│   ├── audit_logger.py
│   ├── controller.py
│   ├── llm_engine.py
│   ├── sql_connector.py
│   ├── tool_registry.py
│   ├── tools.py
│   ├── versioning.py
├── config/
│   └── database_config.py
├── data/audit/
│   └── chat_audit.db (auto-created)
├── Dockerfile
├── launch.py
├── .env
├── requirements.txt
└── README.md

## 🚀 Quickstart

```bash
# Clone repo
git clone https://github.com/orobertg/sqlchatbot
cd sqlchatbot

# PipEnv (virtual environment)
pipenv shell

# Install dependencies
pip install -r requirements.txt

# Add your .env file
cp .env.example .env
# Edit your database + model settings

# Run app
streamlit run app/streamlit_app.py

# Use CTL+C to interrupt the streamlit app server and exit

# Docker 
docker-compose up --build

# Rebuild Clean if needed
docker-compose down
docker-compose up --build