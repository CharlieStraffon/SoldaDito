"""Herramientas (F7): hub + Cotización + Revisión de creativos."""
from flask import Blueprint, render_template, request

from ..csrf import require_csrf
from ..database import db
from ..models import Account, Client
from ..services import quoting

tools_bp = Blueprint("tools", __name__)


@tools_bp.route("/herramientas")
def index():
    return render_template("herramientas.html")


@tools_bp.route("/herramientas/cotizacion", methods=["GET", "POST"])
def cotizacion():
    clients = Client.query.order_by(Client.name).all()
    accounts = Account.query.filter(Account.client_id.isnot(None)).order_by(Account.name).all()
    result = None
    form = {}
    if request.method == "POST":
        require_csrf()
        form = request.form
        client = db.session.get(Client, int(form["client_id"])) if form.get("client_id") else None
        margin = _f(form.get("margin")) or (client.effective_margin() if client else 0.35)
        ticket = _f(form.get("ticket"))
        honorarios = _f(form.get("honorarios")) or (client.monthly_fee if client else 0) or 0
        cpa = _f(form.get("cpa"))
        if cpa is None and form.get("baseline_account_id"):
            cpa = quoting.cpa_from_baseline(int(form["baseline_account_id"]))
        objetivo = _f(form.get("objetivo")) or 0
        result = quoting.calc(objetivo, cpa, margin, ticket, honorarios)
        result["client"] = client
    return render_template("cotizacion.html", clients=clients, accounts=accounts,
                           result=result, form=form)


@tools_bp.route("/herramientas/creativos")
def creativos():
    return render_template("creativos.html")


def _f(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None
