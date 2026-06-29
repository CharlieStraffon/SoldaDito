"""Detalle de cuenta por tipo (F3, branded): ecommerce / leads / mensajes."""
from flask import Blueprint, abort, redirect, render_template, request, url_for

from ..constants import ACTION_TYPES, PLATFORM_GOOGLE_ADS
from ..csrf import require_csrf
from ..database import db
from ..models import Account, MeasurementProfile
from ..services import account_detail, periods
from ..services import actions as act_svc

accounts_bp = Blueprint("accounts", __name__)


@accounts_bp.route("/accounts/<int:account_id>")
def detail(account_id):
    account = db.session.get(Account, account_id)
    if account is None:
        abort(404)
    s, e, plabel = periods.resolve(
        request.args.get("period"),
        periods.parse_date(request.args.get("start")),
        periods.parse_date(request.args.get("end")),
    )
    period_key = request.args.get("period") or "30d"
    d = account_detail.build(account, s, e, period_key)
    back_slug = "google" if account.platform == PLATFORM_GOOGLE_ADS else "facebook"
    return render_template(
        "account_detail.html", d=d, back_slug=back_slug,
        action_types=ACTION_TYPES,
        actions=act_svc.recent(account.id),
        measurement=account.measurement,
    )


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
        v = request.form.get(f)
        setattr(mp, f, True if v == "yes" else (False if v == "no" else None))
    mp.primary_conversion_label = request.form.get("primary_conversion_label") or mp.primary_conversion_label
    db.session.commit()
    return redirect(url_for("accounts.detail", account_id=account_id))
