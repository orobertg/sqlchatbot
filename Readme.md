# 🧠 SQL Chatbot – Natural Language to SQL, Powered by Local LLMs

![Python](https://img.shields.io/badge/python-3.12-blue)
![Streamlit](https://img.shields.io/badge/streamlit-1.44%2B-brightgreen)
![License](https://img.shields.io/badge/license-Apache%202.0-yellowgreen)
![Docker](https://img.shields.io/badge/docker-supported-blue)
![Chatbot](https://img.shields.io/badge/chatbot-LLM%20SQL%20Assistant-purple)
![Version](https://img.shields.io/badge/version-1.1.0-informational)
![](https://github.com/orobertg/sqlchatbot/blob/main/sqlchatbot.gif)

A modular, schema-aware chatbot that connects to your SQL Server database and turns natural language into executable SQL queries.

Built with:
- ✅ Streamlit for UI
- ✅ Ollama / Local LLMs (OpenAI Compatible)
- ✅ Microsoft SQL Server + PyODBC
- ✅ SQLite-based Non-Blocking Audit Logging
- ✅ Optional OpenTelemetry Observability

---

## 📂 Folder Structure

```
/sqlchatbot/
├── app/
│   ├── audit_log.py
│   ├── chat.py
│   ├── chat_react.py
│   ├── configuration.py
│   ├── home.py
│   ├── streamlit_app.py
│   └── tools.py
├── backend/
│   ├── audit_logger.py
│   ├── db_tools.py
│   ├── llm_engine.py
│   ├── openai_tool_registry.py
│   ├── sql_connector.py
│   ├── system.py
│   └── tool_registry.py
├── config/
│   └── database_config.py
├── data/
│   ├── audit/          # SQLite audit log (auto-created)
│   └── cache/          # Schema cache JSON files (auto-created)
├── .env
├── .env_template
├── .env_template_docker
├── compose.yaml
├── Dockerfile
├── launch.py
├── Readme.md
└── requirements.txt
```

---

## ⚙️ Configuration

Copy the template and fill in your values before running:

```bash
cp .env_template .env
```

| Variable | Description |
|---|---|
| `CONNECTION_MODE` | `MANUAL` for direct connection string, `DSN` for ODBC DSN |
| `DATABASE_DRIVER` | ODBC driver name, e.g. `{ODBC Driver 17 for SQL Server}` |
| `DATABASE_SERVER` | SQL Server hostname or IP |
| `DATABASE_NAME` | Database to connect to |
| `DATABASE_USER` | SQL Server login |
| `DATABASE_PASSWORD` | SQL Server password |
| `DATABASE_PORT` | Port (default `1433`) |
| `DATABASE_DSN` | DSN name — only used when `CONNECTION_MODE=DSN` |
| `OPENAI_API_BASE` | Ollama API base URL (default `http://localhost:11434/v1`) |
| `OPENAI_API_KEY` | Set to `ollama` when using Ollama |
| `LLM_MODEL` | Model name, e.g. `qwen2.5-coder:7b` |

---

## 🚀 Local Quickstart

Requires Python 3.12 and [Ollama](https://ollama.com) running locally with your chosen model pulled.

```bash
# Clone repo
git clone https://github.com/orobertg/sqlchatbot
cd sqlchatbot

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env_template .env
# Edit .env with your database and model settings

# Run app
streamlit run app/streamlit_app.py
# or
python launch.py
```

Open `http://localhost:8501` in your browser. Use `Ctrl+C` to stop.

---

## 🐳 Docker

### Prerequisites

**1. Create the external Docker network** — the compose file expects a network named `appnet`. This only needs to be done once:

```bash
docker network create --driver bridge appnet
```

**2. Configure your `.env`** using the Docker template (uses `host.docker.internal` to reach Ollama on the host):

```bash
cp .env_template_docker .env
# Edit .env with your database credentials
```

> **Important:** `DATABASE_SERVER` must be reachable from inside the container.
> - Use `host.docker.internal` if SQL Server is running on your host machine.
> - Use the container name if SQL Server is running in Docker (see below).
> - Do **not** use `localhost` — it resolves to the container itself.

> **Important:** `OPENAI_API_BASE` is set to `http://host.docker.internal:11434/v1` in the Docker template so the container can reach Ollama running on your host. Do not change this to `localhost`.

**3. If SQL Server is also running in a container**, connect it to `appnet` so the two containers can reach each other by name:

```bash
docker network connect appnet <sql-server-container-name>
```

### Run

```bash
docker compose up --build
```

Open `http://localhost:8501` in your browser.

### Rebuild clean

```bash
docker compose down
docker compose up --build
```

---

## 🗄️ Database Connection Modes

The app supports two connection modes, configurable via the UI or `.env`:

**Manual (Connection String)** — set `CONNECTION_MODE=MANUAL` and fill in `DATABASE_DRIVER`, `DATABASE_SERVER`, `DATABASE_NAME`, `DATABASE_USER`, `DATABASE_PASSWORD`, and optionally `DATABASE_PORT`.

**ODBC DSN** — set `CONNECTION_MODE=DSN` and provide a `DATABASE_DSN` name along with `DATABASE_USER` and `DATABASE_PASSWORD`. The DSN must be configured on the host (or inside the container for Docker).

---

## 🤖 LLM / Ollama

The app uses [Ollama](https://ollama.com) as its LLM backend via an OpenAI-compatible API. Pull your model before starting:

```bash
ollama pull qwen2.5-coder:7b
```

Any Ollama-compatible model can be used. Set `LLM_MODEL` in `.env` or change it in the Configuration page at runtime.

---

## 📝 Schema Caching

On first connection the app introspects your database and writes a schema cache to `data/cache/`. The cache is valid for 2 hours. To force a refresh, use the **Schema Viewer** tab in the Tools page or delete the cache files manually.

---

## 📋 Changelog

### v1.1.0 — 2026-05-10
**Bug fixes across all core modules**

- **`sql_connector`** — removed dead `cursor()` method that was shadowed by the instance attribute; fixed `validate_db_connection()` crashing with `AttributeError` after calling `connect()` (which returns `None`); fixed `test_db_connection()` passing unsupported keyword arguments to `SQLConnector`
- **`configuration`** — fixed `UnboundLocalError` in `build_connection_string()` when using DSN mode; replaced broken `test_database_connection()` implementation (referenced unimported `SQLConnector`) with delegation to the backend function; replaced removed `st.experimental_rerun()` with `st.rerun()`
- **`tools`** — added missing `import logging.handlers` and `logger` definition that caused `AttributeError`/`NameError` on the Tools page; replaced `st.experimental_rerun()` calls
- **`chat`** — guarded all `debug_info` key accesses in `get_bot_response()` so a failed LLM call no longer raises `KeyError`
- **`llm_engine`** — initialized `connector = None` before the try block in `_build_schema_map()` to prevent `NameError` in the except handler
- **`db_tools`** — fixed integer index access on dict query results in `get_databases()` and `get_all_schema_names()`; fixed `describe_table()` tuple unpacking and row access; added guard for unqualified table names in `validate_query()`; fixed `get_schema_map_formatted()` iterating dict-based columns as a list; fixed `build_visual_query()` column name extraction; fixed `list_tables()` using named param syntax (`:schema_name`) incompatible with pyodbc — replaced with `?` placeholder

### v1.0.0 — Initial release
- Streamlit UI with chat and configuration pages
- Schema-aware SQL generation via local LLMs (Ollama)
- SQL Server connectivity via PyODBC (Manual and DSN modes)
- Schema introspection with 2-hour file cache
- SQLite audit logging
- Docker support
