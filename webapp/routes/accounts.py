"""Detalle de cuenta por tipo (F3). Stub en F0."""
from flask import Blueprint, render_template

accounts_bp = Blueprint("accounts", __name__)


@accounts_bp.route("/accounts/<int:account_id>")
def detail(account_id):
    return render_template("placeholder.html", title=f"Cuenta {account_id}", phase="F3")
