"""Instancia de SQLAlchemy + PRAGMAs de SQLite (WAL, FK, busy_timeout)."""
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()


@event.listens_for(Engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record):
    """Por conexión: WAL (lecturas concurrentes), FK on, espera ante locks."""
    # Solo aplica a SQLite; otros motores ignoran.
    module = type(dbapi_connection).__module__
    if "sqlite" not in module:
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()
