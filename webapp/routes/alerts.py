"""Alertas críticas + ruteo (F5). Stub en F0."""
from flask import Blueprint, render_template

alerts_bp = Blueprint("alerts", __name__)


@alerts_bp.route("/alertas")
def index():
    return render_template("placeholder.html", title="Alertas", phase="F5")
