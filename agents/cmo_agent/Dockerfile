FROM python:3.11-slim

# Install system dependencies including FFmpeg and curl
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependencies first to leverage caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

EXPOSE 8090

# Run FastAPI app
CMD ["python", "agent.py"]
