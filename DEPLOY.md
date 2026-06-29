# Deploy de DITO en EasyPanel

App Flask + gunicorn + **SQLite (WAL)**. La base vive en `instance/dito.db` y **debe ir en un
volumen persistente** o se pierde en cada redeploy.

## 1. Repo en GitHub
```bash
git remote add origin git@github.com:<usuario>/<repo>.git   # o https://...
git push -u origin main
```
`.env` y `instance/*.db` están en `.gitignore` — las llaves NO se suben.

## 2. Crear la app en EasyPanel
- **New → App → Source: GitHub** → elige el repo y la rama `main`.
- **Build: Dockerfile** (en la raíz; EasyPanel lo detecta).
- **Port:** `8000`.

## 3. Volumen persistente para la base  ← lo más importante
- En la app → **Mounts / Volumes → Add Volume**:
  - **Mount path:** `/app/instance`
  - (nombre del volumen: `dito-instance`)
- Así `dito.db` (+ `-wal`/`-shm`) sobrevive a redeploys. El `Dockerfile` ya declara `VOLUME /app/instance`.

## 4. Variables de entorno (Environment)
Mínimas:
```
SECRET_KEY=<una-cadena-larga-aleatoria>
FLASK_ENV=production
DATABASE_URL=sqlite:///instance/dito.db
ANTHROPIC_API_KEY=...            # Haiku triage / Sonnet reportes
ANTHROPIC_MODEL_TRIAGE=claude-haiku-4-5-20251001
ANTHROPIC_MODEL_ANALYST=claude-sonnet-4-6
```
Para **sync en vivo** (Meta/Google) añade además las llaves del `.env.example`
(`GOOGLE_ADS_*`, `FACEBOOK_ADS_*`) y, en el build, instala `requirements-sync.txt`
(o agrégalo al Dockerfile). Sin esas libs/llaves la app corre, pero no sincroniza.

## 5. Inicializar la base (una sola vez)
`docker-entrypoint.sh` corre `scripts.init_db` en cada arranque (crea tablas faltantes,
**no borra ni altera** — idempotente). El **seed** NO corre solo. Elige UNA opción:

**Opción A — subir la base ya sembrada (recomendada para el día 1).**
Tu `instance/dito.db` local ya tiene el roster real (35 cuentas) + 13k métricas.
Súbela al volumen `/app/instance` (EasyPanel → File manager del volumen, o `scp`/`docker cp`).
Listo: la app arranca con datos.

**Opción B — sembrar en el servidor.**
Requiere las libs de sync + llaves (paso 4) para jalar el roster de la API.
Primer deploy: pon `SEED_ON_START=1` en Environment, despliega una vez, y **quítalo** después
(para no re-seed en cada deploy). El seed es idempotente: no pisa ediciones ni meses cerrados.

> Redeploys posteriores: no toques nada de la base. El volumen + `init_db` idempotente la preservan.
> Para migraciones de esquema futuras usa Flask-Migrate (`flask db upgrade`); el build actual crea
> el esquema fresco con `init_db` (greenfield).

## 6. Verificar
- `https://<tu-dominio>/healthz` → `{"status":"ok","db":true,...}`
- `https://<tu-dominio>/` → centro de control (redirige a `/google`).

## 7. Seguridad (antes de exponer público)
La app **no tiene autenticación** todavía. Restríngela en EasyPanel (Basic Auth / IP allowlist)
o agrega login (el legacy usaba OAuth de Google Workspace) antes de publicarla abierta.

## 8. Backups
La base es un archivo. Respáldala con:
```bash
sqlite3 /app/instance/dito.db ".backup /app/instance/backup-$(date +%F).db"
```
(o snapshot del volumen en EasyPanel).
