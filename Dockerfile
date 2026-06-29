# DITO / SoldaDito — imagen de producción
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FLASK_ENV=production

WORKDIR /app

# curl para el healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Dependencias core (los clients de API se importan perezosamente; para sync en vivo
# añade requirements-sync.txt en una capa posterior o como build-arg).
COPY requirements.txt requirements-sync.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p instance && chmod +x docker-entrypoint.sh

# La base SQLite vive en /app/instance — MONTAR un volumen persistente ahí.
VOLUME ["/app/instance"]

# Puerto interno por defecto. EasyPanel debe apuntar su proxy a ESTE puerto (8000).
# Si EasyPanel inyecta $PORT, gunicorn_conf lo respeta automáticamente.
ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=5 \
    CMD curl -fsS "http://127.0.0.1:${PORT:-8000}/healthz" || exit 1

# Invocado con `sh` para evitar problemas de bit-ejecutable / fin de línea.
CMD ["sh", "docker-entrypoint.sh"]
