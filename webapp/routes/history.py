"""Desglose mensual editable + cierre de mes (F4, branded)."""
from flask import (Blueprint, abort, flash, jsonify, redirect, render_template,
                   request, url_for)

from ..constants import PLATFORM_GOOGLE_ADS, PLATFORMS
from ..csrf import require_csrf
from ..database import db
from ..models import Account
from ..services import desglose

history_bp = Blueprint("history", __name__)


def _platform():
    p = request.args.get("platform")
    return p if p in PLATFORMS else PLATFORM_GOOGLE_ADS


@history_bp.route("/desglose")
def index():
    platform = _platform()
    accts = desglose.classified_accounts(platform)
    if not accts:
        return render_template("desglose.html", d=None, platform=platform,
                               platform_counts=desglose.platform_counts(), accounts=[])
    return redirect(url_for("history.account", account_id=accts[0].id, platform=platform))


@history_bp.route("/desglose/<int:account_id>")
def account(account_id):
    acct = db.session.get(Account, account_id)
    if not acct:
        abort(404)
    platform = request.args.get("platform") or acct.platform
    d = desglose.context(acct)
    return render_template(
        "desglose.html", d=d, platform=platform,
        platform_counts=desglose.platform_counts(),
        accounts=desglose.classified_accounts(platform),
        valid_types=desglose.VALID_TYPES,
    )


@history_bp.route("/desglose/<int:account_id>/cell", methods=["POST"])
def cell(account_id):
    require_csrf()
    acct = db.session.get(Account, account_id)
    if not acct:
        return jsonify({"ok": False, "error": "cuenta no encontrada"}), 404
    try:
        year = int(request.form["year"]); month = int(request.form["month"])
    except (KeyError, ValueError):
        return jsonify({"ok": False, "error": "periodo inválido"}), 400
    result = desglose.update_cell(acct, year, month, request.form.get("field"),
                                  request.form.get("value"))
    return jsonify(result)


@history_bp.route("/desglose/<int:account_id>/set-type", methods=["POST"])
def set_type(account_id):
    require_csrf()
    acct = db.session.get(Account, account_id)
    if not acct:
        abort(404)
    desglose.set_objetivo(acct, request.form.get("client_type"))
    return redirect(url_for("history.account", account_id=account_id, platform=acct.platform))


@history_bp.route("/desglose/<int:account_id>/close", methods=["POST"])
def close_month(account_id):
    require_csrf()
    acct = db.session.get(Account, account_id)
    if not acct:
        abort(404)
    year = int(request.form["year"]); month = int(request.form["month"])
    ok = desglose.close_month(acct, year, month)
    flash("Mes cerrado: margen y fee congelados." if ok else "No se pudo cerrar.", "success" if ok else "warning")
    return redirect(url_for("history.account", account_id=account_id, platform=acct.platform))


@history_bp.route("/desglose/<int:account_id>/close-history", methods=["POST"])
def close_history(account_id):
    require_csrf()
    acct = db.session.get(Account, account_id)
    if not acct:
        abort(404)
    n = desglose.close_history(acct)
    flash(f"{n} mes(es) cerrados. 'Tu normal' actualizado.", "success")
    return redirect(url_for("history.account", account_id=account_id, platform=acct.platform))
