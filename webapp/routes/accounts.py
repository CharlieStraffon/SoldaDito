"""Detalle de cuenta por tipo (F3): ecommerce (ROAS+embudo) / leads (costo/result.)."""
from flask import Blueprint, abort, render_template, request

from ..constants import ACTION_TYPES
from ..csrf import require_csrf
from ..database import db
from ..models import Account, MeasurementProfile
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
    return render_template("account_detail.html", preset=plabel, action_types=ACTION_TYPES, **ctx)


_BOOL_FIELDS = ("pixel_ok", "capi_ok", "ga4_linked", "enhanced_conversions",
                "offline_import", "domain_verified", "consent_mode")


@accounts_bp.route("/accounts/<int:account_id>/measurement", methods=["POST"])
def measurement(account_id):
    require_csrf()
    account = db.session.get(Account, account_id)
    if account is None:
        abort(404)
    mp = account.measurement
    if mp is None:
        mp = MeasurementProfile(account_id=account.id)
        db.session.add(mp)
    for f in _BOOL_FIELDS:
        mp_val = request.form.get(f)
        setattr(mp, f, True if mp_val == "yes" else (False if mp_val == "no" else None))
    mp.primary_conversion_label = request.form.get("primary_conversion_label") or mp.primary_conversion_label
    db.session.commit()
    return redirect(url_for("accounts.detail", account_id=account_id))
