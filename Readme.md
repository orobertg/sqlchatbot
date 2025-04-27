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
├── .env
├── .env_template_docker
├── compose.yml
├── Dockerfile
├── launch.py
├── README.md
└── requirements.txt

![sqlchatbot](https://github.com/orobertg/sqlchatbot/blob/main/sqlchatbot.gif)

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
# copy .env_template .env if you haven't done so
cp .env_template .env 
# create a docker network, docker compose expects this appnet docker network
# bridge is the default network.
docker network create --driver bridge appnet
# if you are running MS SQL Server in a container, add it to the appnet network
docker network connect appnet sql1
# build the sqlchatbot app image and run the app from container
docker-compose up --build

# Rebuild Clean if needed, tear-down and build up
docker-compose down
docker-compose up --build