"""Administración: cuentas pendientes_de_clasificar + UIs de edición (F7). Stub en F0."""
from flask import Blueprint, render_template

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/admin")
def index():
    return render_template("placeholder.html", title="Administración", phase="F7")
