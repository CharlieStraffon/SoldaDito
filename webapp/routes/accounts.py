"""Detalle de cuenta por tipo (F3): ecommerce (ROAS+embudo) / leads (costo/result.)."""
from flask import Blueprint, abort, render_template, request

from ..database import db
from ..models import Account
from ..services import account_detail, periods

accounts_bp = Blueprint("accounts", __name__)


@accounts_bp.route("/accounts/<int:account_id>")
def detail(account_id):
    account = db.session.get(Account, account_id)
    if account is None:
        abort(404)
    s, e, plabel = periods.resolve(
        request.args.get("preset"),
        periods.parse_date(request.args.get("start")),
        periods.parse_date(request.args.get("end")),
    )
    ctx = account_detail.build(account, s, e)
    return render_template("account_detail.html", preset=plabel, **ctx)
