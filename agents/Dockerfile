FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PORT=8080 \
    APP_HOME=/app

WORKDIR $APP_HOME

# Install system dependencies (needed for standard tools/harness if any, and certificates)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY cmo_agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY cmo_agent/ ./cmo_agent

# Expose port
EXPOSE 8080

# Command to run the service
CMD ["python", "cmo_agent/agent.py"]
