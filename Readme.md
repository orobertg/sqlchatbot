# 🧠 SQL Chatbot – Natural Language to SQL, Powered by Local LLMs

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
git clone https://github.com/orobertgyourname/sqlchatbot
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
