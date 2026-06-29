"""Config de gunicorn para producción.

SQLite (WAL) tolera lecturas concurrentes; las escrituras serializan con busy_timeout.
Para esta herramienta interna, pocos workers + hilos es lo correcto (no saturar el lock).
"""
import os

bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
workers = int(os.getenv("GUNICORN_WORKERS", "2"))
threads = int(os.getenv("GUNICORN_THREADS", "4"))
worker_class = "gthread"
timeout = 120
graceful_timeout = 30
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info")
