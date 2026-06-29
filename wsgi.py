"""Entry point WSGI / dev server.

En producción lo sirve gunicorn (`gunicorn wsgi:app`). Si por alguna razón el host
ejecuta `python wsgi.py`, igual escuchamos en 0.0.0.0:$PORT para ser ALCANZABLES
(no en 127.0.0.1, que dejaría la app inaccesible detrás del proxy).
"""
import os

from webapp import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=app.config.get("DEBUG", False))
