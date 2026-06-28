"""Centro de control (F3). Stub en F0; se completa en F3."""
from flask import Blueprint, render_template

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def index():
    return render_template("placeholder.html", title="Centro de control", phase="F3")
