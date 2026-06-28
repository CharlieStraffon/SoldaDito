"""Administración (F7): reclasificar pendientes + editar margen/targets/fee."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from ..constants import (
    CAPTURE_METHODS,
    PANEL_TYPES,
    PLATFORM_LABELS,
    PURPOSES,
    VALUE_SOURCES,
)
from ..csrf import require_csrf
from ..database import db
from ..models import Account, Client
from ..services import admin as admin_svc
from ..services import categorization as cat

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/admin")
def index():
    accounts = Account.query.order_by(Account.platform, Account.name).all()
    pending = [a for a in accounts if cat.is_pending(a)]
    clients = Client.query.order_by(Client.name).all()
    return render_template(
        "admin.html", pending=pending, clients=clients, accounts=accounts,
        panel_types=PANEL_TYPES, capture_methods=CAPTURE_METHODS,
        value_sources=VALUE_SOURCES, purposes=PURPOSES, platform_labels=PLATFORM_LABELS,
    )


@admin_bp.route("/admin/account/<int:account_id>/classify", methods=["POST"])
def classify(account_id):
    require_csrf()
    a = db.session.get(Account, account_id)
    if not a:
        abort(404)
    admin_svc.classify_account(
        a,
        client_id=request.form.get("client_id") or None,
        panel_type=request.form.get("panel_type"),
        capture_methods=request.form.getlist("capture_methods"),
        primary_capture=request.form.get("primary_capture"),
        value_source=request.form.get("value_source"),
        purpose=request.form.get("purpose"),
        location_label=request.form.get("location_label"),
    )
    flash(f"Cuenta «{a.name}» clasificada.", "success")
    return redirect(url_for("admin.index"))


@admin_bp.route("/admin/client/<int:client_id>/margin", methods=["POST"])
def margin(client_id):
    require_csrf()
    c = db.session.get(Client, client_id)
    if not c:
        abort(404)
    admin_svc.set_margin(c, request.form["margin_pct"])
    flash(f"Margen de {c.name} = {c.margin_pct:.0%}.", "success")
    return redirect(url_for("admin.index"))


@admin_bp.route("/admin/account/<int:account_id>/targets", methods=["POST"])
def targets(account_id):
    require_csrf()
    a = db.session.get(Account, account_id)
    if not a:
        abort(404)
    admin_svc.set_targets(
        a,
        target_cpa=request.form.get("target_cpa"),
        target_roas=request.form.get("target_roas"),
        monthly_budget=request.form.get("monthly_budget"),
        monthly_fee=request.form.get("monthly_fee"),
    )
    flash(f"Objetivos de «{a.name}» actualizados.", "success")
    return redirect(url_for("admin.index"))
