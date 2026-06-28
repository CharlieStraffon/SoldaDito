"""Health check (público)."""
from flask import Blueprint, jsonify

from ..database import db
from ..models import Account, Client

health_bp = Blueprint("health", __name__)


@health_bp.route("/healthz")
def healthz():
    try:
        clients = Client.query.count()
        accounts = Account.query.count()
        db_ok = True
    except Exception:  # noqa
        clients = accounts = 0
        db_ok = False
    return jsonify({"status": "ok", "db": db_ok, "clients": clients, "accounts": accounts})
