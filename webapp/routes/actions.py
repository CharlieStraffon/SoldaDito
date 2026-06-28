"""ActionLog (F6). Stub en F0."""
from flask import Blueprint, render_template

actions_bp = Blueprint("actions", __name__)


@actions_bp.route("/acciones")
def index():
    return render_template("placeholder.html", title="Registro de acciones", phase="F6")
