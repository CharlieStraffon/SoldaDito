.PHONY: venv install run schema migrate seed test lint diag clean

PY ?= .venv/bin/python
PIP ?= .venv/bin/pip

venv:
	python3 -m venv .venv

install: venv
	$(PIP) install -U pip
	$(PIP) install -r requirements.txt

# Crea el esquema fresco (greenfield). NO altera columnas existentes.
schema:
	$(PY) -m scripts.init_db

# Migraciones incrementales (Flask-Migrate / Alembic) — para cambios futuros.
migrate:
	FLASK_APP=wsgi.py $(PY) -m flask db upgrade

seed:
	$(PY) -m scripts.seed

run:
	FLASK_ENV=development $(PY) wsgi.py

test:
	$(PY) -m pytest -q

# Diagnóstico de fin de fase: esquema + seed idempotente + tests + boot.
diag:
	$(PY) -m scripts.diagnostic

clean:
	rm -f instance/dito.db instance/dito.db-wal instance/dito.db-shm
