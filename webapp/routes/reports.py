"""Generador de reportes (F7 reskin; motor se mantiene). Stub en F0."""
from flask import Blueprint, render_template

reports_bp = Blueprint("reports", __name__)


@reports_bp.route("/reportes")
def index():
    return render_template("placeholder.html", title="Reportes", phase="F7")
