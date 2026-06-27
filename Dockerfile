FROM python:3.12-slim

WORKDIR /app

# Dependencias del sistema para psycopg2
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway inyecta PORT como variable de entorno
ENV MCP_HOST=0.0.0.0
CMD python server.py
