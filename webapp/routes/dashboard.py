"""Centro de control (F3) — página de marca por plataforma (Google/Facebook)."""
from flask import Blueprint, redirect, render_template, request, url_for

from ..services import briefing

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def root():
    return redirect(url_for("dashboard.index", slug="google"))


@dashboard_bp.route("/<any(google, facebook):slug>")
def index(slug):
    period = request.args.get("period")
    ctx = briefing.build(slug, period)
    return render_template("centro.html", **ctx)
