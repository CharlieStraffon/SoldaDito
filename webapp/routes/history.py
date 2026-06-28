"""Desglose mensual + cierre de mes (F4). Stub en F0."""
from flask import Blueprint, render_template

history_bp = Blueprint("history", __name__)


@history_bp.route("/desglose")
def index():
    return render_template("placeholder.html", title="Desglose mensual", phase="F4")
