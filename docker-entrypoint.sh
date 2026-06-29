#!/usr/bin/env sh
# Arranque de producción. La base vive en el volumen /app/instance.
set -e

# Crea las tablas faltantes (create_all NO altera columnas existentes ni borra datos).
# Idempotente: seguro en cada redeploy.
python -m scripts.init_db

# Seed bajo demanda (NO automático en cada deploy para no pisar datos).
# Pon SEED_ON_START=1 en EasyPanel solo para el PRIMER arranque, luego quítalo.
if [ "$SEED_ON_START" = "1" ]; then
  echo "[entrypoint] SEED_ON_START=1 -> corriendo seed idempotente"
  python -m scripts.seed || echo "[entrypoint] seed falló (continuando)"
fi

exec gunicorn -c gunicorn_conf.py wsgi:app
