"""Crea el esquema fresco (greenfield). create_all NO altera columnas existentes."""
import sys

from webapp import create_app
from webapp.database import db
# Importa todos los modelos para registrarlos en el metadata.
from webapp import models  # noqa: F401


def main():
    app = create_app()
    with app.app_context():
        db.create_all()
        tables = sorted(db.metadata.tables.keys())
        print(f"[init_db] esquema creado. {len(tables)} tablas:")
        for t in tables:
            print(f"  · {t}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
