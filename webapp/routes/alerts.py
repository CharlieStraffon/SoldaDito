"""Alertas críticas + ruteo (F5)."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from ..constants import (
    ALERT_ACKNOWLEDGED,
    ALERT_RESOLVED,
    PLATFORM_LABELS,
    SEVERITY_CRITICAL,
    SEVERITY_PERFORMANCE,
    SEVERITY_POSITIVE,
)
from ..csrf import require_csrf
from ..database import db
from ..models import Alert, TeamMember
from ..services import alerts as alert_svc
from ..services import triage

alerts_bp = Blueprint("alerts", __name__)


@alerts_bp.route("/alertas")
def index():
    status = request.args.get("status", "active")
    member = request.args.get("member")
    q = Alert.query
    if status == "active":
        q = q.filter(Alert.status != ALERT_RESOLVED)
    elif status in (ALERT_ACKNOWLEDGED, ALERT_RESOLVED, "new"):
        q = q.filter(Alert.status == status)
    if member:
        tm = TeamMember.query.filter_by(slug=member).first()
        if tm:
            q = q.filter(Alert.routed_to_id == tm.id)
    alerts = q.order_by(Alert.date.desc()).all()

    buckets = {SEVERITY_CRITICAL: [], SEVERITY_PERFORMANCE: [], SEVERITY_POSITIVE: []}
    for a in alerts:
        buckets.setdefault(a.severity, []).append(a)
    return render_template(
        "alerts.html", buckets=buckets, platform_labels=PLATFORM_LABELS,
        members=TeamMember.query.all(), status=status, member=member,
        sev_labels={SEVERITY_CRITICAL: "Críticas", SEVERITY_PERFORMANCE: "Rendimiento",
                    SEVERITY_POSITIVE: "Positivas"},
    )


@alerts_bp.route("/alertas/run", methods=["POST"])
def run():
    require_csrf()
    result = alert_svc.run_detection()
    flash(f"Detección: {result['critical']} críticas de {result['alerts']} alertas "
          f"({result['accounts']} cuentas, datos al {result.get('as_of','—')}).", "info")
    return redirect(url_for("alerts.index"))


@alerts_bp.route("/alertas/<int:alert_id>/<action>", methods=["POST"])
def update(alert_id, action):
    require_csrf()
    a = db.session.get(Alert, alert_id)
    if not a:
        abort(404)
    if action == "ack":
        a.status = ALERT_ACKNOWLEDGED
    elif action == "resolve":
        a.status = ALERT_RESOLVED
    elif action == "explain":
        triage.explain(a, force=True)
    db.session.commit()
    return redirect(request.referrer or url_for("alerts.index"))
