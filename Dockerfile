# Base image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Create working directory
WORKDIR /app

# Install dependencies
COPY .env_template .env
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose Streamlit default port
EXPOSE 8502

# Set PYTHONPATH
ENV PYTHONPATH=/app

# Streamlit specific environment variables (avoid opening browser, set host)
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_PORT=8502
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Command to run the app
CMD ["streamlit", "run", "app/streamlit_app.py"]
