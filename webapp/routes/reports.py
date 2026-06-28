"""Generador de reportes (F7 reskin; el motor se mantiene)."""
from flask import Blueprint, abort, render_template, request

from ..constants import PLATFORM_LABELS, PLATFORMS
from ..database import db
from ..models import Client
from ..services import engagement as eng
from ..services import metrics
from ..services import report_builder

reports_bp = Blueprint("reports", __name__)


def _period():
    d = metrics.latest_metric_date()
    y, m = (d.year, d.month) if d else (2026, 6)
    try:
        y = int(request.args.get("year", y)); m = int(request.args.get("month", m))
    except (TypeError, ValueError):
        pass
    return y, m


@reports_bp.route("/reportes")
def index():
    year, month = _period()
    groups = eng.list_engagements(only_active=True)
    items = []
    for (client_id, platform), accts in groups.items():
        c = db.session.get(Client, client_id)
        if c:
            items.append({"client": c, "platform": platform, "n": len(accts)})
    items.sort(key=lambda x: x["client"].name)
    return render_template("reportes_list.html", items=items, year=year, month=month,
                           platform_labels=PLATFORM_LABELS)


@reports_bp.route("/reportes/<client_slug>/<platform>")
def report(client_slug, platform):
    c = Client.query.filter_by(slug=client_slug).first()
    if not c or platform not in PLATFORMS:
        abort(404)
    year, month = _period()
    data = report_builder.build(c, platform, year, month)
    show_narrative = request.args.get("narrative") == "1"
    narrative = report_builder.narrative(data) if show_narrative else None
    return render_template("reporte.html", platform_labels=PLATFORM_LABELS,
                           narrative=narrative, **data)
