# Dockerfile optimizado para Railway
FROM python:3.12-slim

# Variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && \
    apt-get install -y curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar código de la aplicación
COPY . .

# Exponer puerto
EXPOSE 8000

# Comando de inicio con logging detallado
CMD ["sh", "-c", "echo '🚀 Starting Railway deployment' && echo 'Port: ${PORT:-8000}' && echo 'Environment: ${ENVIRONMENT:-development}' && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --log-level info --access-log"]