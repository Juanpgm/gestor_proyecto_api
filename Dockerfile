# Railway deployment Dockerfile
FROM python:3.12-slim

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (Railway will set PORT env var dynamically)
EXPOSE $PORT

# Start command - Let Railway set the port
CMD ["sh", "-c", "echo 'Starting Railway deployment' && echo 'Port: ${PORT:-8000}' && echo 'Environment: ${ENVIRONMENT:-development}' && exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --log-level info --access-log"]