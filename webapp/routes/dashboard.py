"""Centro de control (F3): resumen ejecutivo escaneable, peor-primero, por plataforma."""
from flask import Blueprint, render_template, request

from ..constants import PLATFORM_LABELS, PLATFORMS
from ..services import dashboard as dash_svc
from ..services import periods

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def index():
    preset = request.args.get("preset")
    start = periods.parse_date(request.args.get("start"))
    end = periods.parse_date(request.args.get("end"))
    s, e, plabel = periods.resolve(preset, start, end)
    summary = dash_svc.build_summary(s, e)
    return render_template(
        "dashboard.html",
        summary=summary,
        start=s,
        end=e,
        preset=plabel,
        preset_labels=periods.PRESET_LABELS,
        presets=periods.PRESETS,
        platforms=PLATFORMS,
        platform_labels=PLATFORM_LABELS,
    )
