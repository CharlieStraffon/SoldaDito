"""ActionLog (F6): registro de acciones (presupuestos con histórico + hipótesis)."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from ..constants import ACTION_BUDGET_CHANGE, ACTION_TYPES, PLATFORM_LABELS
from ..csrf import require_csrf
from ..database import db
from ..models import Account
from ..services import actions as act_svc

actions_bp = Blueprint("actions", __name__)


@actions_bp.route("/acciones")
def index():
    action_type = request.args.get("type")
    entries = act_svc.all_actions(action_type=action_type)
    return render_template("actions.html", entries=entries, action_types=ACTION_TYPES,
                           current_type=action_type, platform_labels=PLATFORM_LABELS)


@actions_bp.route("/acciones/account/<int:account_id>/new", methods=["POST"])
def create(account_id):
    require_csrf()
    account = db.session.get(Account, account_id)
    if not account:
        abort(404)
    action_type = request.form.get("action_type", "hypothesis")
    note = request.form.get("note")
    if action_type == ACTION_BUDGET_CHANGE:
        act_svc.change_budget(account, request.form.get("new_value"), note=note)
        flash("Cambio de presupuesto registrado (con histórico).", "success")
    else:
        act_svc.log_action(account, action_type,
                           old_value=request.form.get("old_value"),
                           new_value=request.form.get("new_value"), note=note)
        flash("Acción registrada.", "success")
    return redirect(request.referrer or url_for("accounts.detail", account_id=account_id))
