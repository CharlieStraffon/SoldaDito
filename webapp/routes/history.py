"""Desglose mensual + cierre de mes (F4)."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from ..constants import PLATFORM_LABELS, PLATFORMS
from ..csrf import require_csrf
from ..database import db
from ..models import Account, Client
from ..services import history as hist
from ..services import metrics
from ..services import engagement as eng

history_bp = Blueprint("history", __name__)


def _default_period():
    d = metrics.latest_metric_date()
    return (d.year, d.month) if d else (2026, 6)


def _period_from_request():
    y, m = _default_period()
    try:
        y = int(request.args.get("year", y))
        m = int(request.args.get("month", m))
    except (TypeError, ValueError):
        pass
    return y, m


@history_bp.route("/desglose")
def index():
    year, month = _period_from_request()
    groups = eng.list_engagements(only_active=True)
    cards = []
    for (client_id, platform), accounts in groups.items():
        client = db.session.get(Client, client_id)
        if not client:
            continue
        em = eng.compute_month(client, platform, year, month)
        cards.append({"client": client, "platform": platform, "metrics": em,
                      "n_accounts": len(accounts)})
    # Peor-primero: por ROI ascendente (los no rentables arriba), None al final.
    cards.sort(key=lambda c: (c["metrics"]["roi"] if c["metrics"] and c["metrics"]["roi"] is not None else 9e9))
    return render_template("desglose_list.html", cards=cards, year=year, month=month,
                           platform_labels=PLATFORM_LABELS)


@history_bp.route("/desglose/<client_slug>/<platform>")
def engagement(client_slug, platform):
    client = Client.query.filter_by(slug=client_slug).first()
    if not client or platform not in PLATFORMS:
        abort(404)
    year, month = _period_from_request()
    view = hist.breakdown(client, platform, year, month)
    return render_template("desglose_engagement.html", platform_labels=PLATFORM_LABELS, **view)


@history_bp.route("/desglose/account/<int:account_id>/save", methods=["POST"])
def save(account_id):
    require_csrf()
    account = db.session.get(Account, account_id)
    if not account:
        abort(404)
    year = int(request.form["year"])
    month = int(request.form["month"])
    _, err = hist.save_manual(account, year, month, request.form)
    flash(err or "Captura guardada.", "warning" if err else "success")
    return redirect(url_for("history.engagement", client_slug=account.client.slug,
                            platform=account.platform, year=year, month=month))


@history_bp.route("/desglose/<client_slug>/<platform>/close", methods=["POST"])
def close(client_slug, platform):
    require_csrf()
    client = Client.query.filter_by(slug=client_slug).first()
    if not client or platform not in PLATFORMS:
        abort(404)
    year = int(request.form["year"])
    month = int(request.form["month"])
    n = hist.close_engagement(client, platform, year, month)
    flash(f"Mes cerrado para {n} cuenta(s). Margen y fee congelados.", "success")
    return redirect(url_for("history.engagement", client_slug=client_slug, platform=platform,
                            year=year, month=month))


@history_bp.route("/desglose/<client_slug>/<platform>/reopen", methods=["POST"])
def reopen(client_slug, platform):
    require_csrf()
    client = Client.query.filter_by(slug=client_slug).first()
    if not client or platform not in PLATFORMS:
        abort(404)
    year = int(request.form["year"])
    month = int(request.form["month"])
    hist.reopen_engagement(client, platform, year, month)
    flash("Mes reabierto.", "info")
    return redirect(url_for("history.engagement", client_slug=client_slug, platform=platform,
                            year=year, month=month))
