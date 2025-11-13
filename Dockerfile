# Use slim python image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Create working directory
WORKDIR /app

# Install dependencies
COPY .env_template_docker .env
COPY requirements.txt .

# Install system dependencies for docker image
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    gnupg2 \
    unixodbc \
    unixodbc-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Microsoft ODBC Driver 17 (optional if using MS SQL Server)
# Modern approach: use gpg keyring in the location Microsoft repo expects
RUN mkdir -p /usr/share/keyrings \
    && curl https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && curl https://packages.microsoft.com/config/debian/12/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql17 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies, excluding Windows-only packages like pywin32
# Handle encoding issues: convert UTF-16 to UTF-8 if needed, then filter
RUN python3 -c "import sys; d=open('requirements.txt','rb').read(); exec('try:\n t=d.decode(\"utf-8\")\nexcept UnicodeDecodeError:\n t=d.decode(\"utf-16-le\")'); lines=[l for l in t.splitlines() if l.strip() and 'pywin32' not in l.lower()]; open('requirements-docker.txt','w',encoding='utf-8').write('\n'.join(lines))"
RUN pip install --no-cache-dir -r requirements-docker.txt && \
    rm requirements-docker.txt && \
    which streamlit || (echo "ERROR: streamlit not installed" && exit 1)

# Copy application files
COPY . .

# Expose Streamlit default port
EXPOSE 8501

# Set PYTHONPATH
ENV PYTHONPATH=/app

# Streamlit specific environment variables (avoid opening browser, set host)
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Ollama
ENV OLLAMA_HOST=0.0.0.0

# Command to run the app
CMD ["streamlit", "run", "app/streamlit_app.py"]
