# Use slim python image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Create working directory
WORKDIR /app

# Install dependencies
COPY .env_template .env
COPY requirements.txt .

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    gnupg2 \
    unixodbc \
    unixodbc-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Microsoft ODBC Driver 17 (optional if using MS SQL Server)
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/debian/10/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql17

RUN pip install --no-cache-dir -r requirements.txt



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

# Command to run the app
CMD ["streamlit", "run", "app/streamlit_app.py"]
