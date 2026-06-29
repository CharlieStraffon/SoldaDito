#!/usr/bin/env sh
# Arranque de producción. La base vive en el volumen /app/instance.
# NO usamos `set -e`: si init_db tiene un problema, igual levantamos gunicorn
# para que la app sea ALCANZABLE y el error se vea en /healthz y en los logs
# (mejor que un contenedor que muere y queda "unreachable").

PORT="${PORT:-8000}"
echo "[entrypoint] arrancando DITO · puerto ${PORT}"

# Crea las tablas faltantes (idempotente; no borra ni altera columnas existentes).
python -m scripts.init_db || echo "[entrypoint] WARN: init_db falló (continuo de todos modos)"

# Seed bajo demanda (NO automático). Pon SEED_ON_START=1 solo el primer arranque.
if [ "$SEED_ON_START" = "1" ]; then
  echo "[entrypoint] SEED_ON_START=1 -> seed idempotente"
  python -m scripts.seed || echo "[entrypoint] WARN: seed falló (continuo)"
fi

echo "[entrypoint] lanzando gunicorn en 0.0.0.0:${PORT}"
exec gunicorn -c gunicorn_conf.py wsgi:app
