"""Construye el detalle de una cuenta (panel por tipo)."""
from ..constants import ALERT_RESOLVED, PANEL_ECOMMERCE
from ..models import Alert
from . import categorization as cat
from . import metrics


def build(account, start, end):
    agg = metrics.aggregate_account(account.id, start, end) or {}
    p_start, p_end = metrics.prior_period(start, end)
    prev = metrics.aggregate_account(account.id, p_start, p_end) or {}
    row = metrics.account_row(account, agg, prev)
    daily = metrics.account_daily(account.id, start, end)
    summary = cat.summary(account)

    funnel = None
    if cat.panel_of(account) == PANEL_ECOMMERCE:
        funnel = {
            "clicks": agg.get("clicks", 0),
            "add_to_cart": agg.get("add_to_cart", 0),
            "checkout": agg.get("initiate_checkout", 0),
            "purchases": agg.get("purchases", 0) or agg.get("conversions", 0),
        }

    active_alerts = (
        Alert.query.filter(Alert.account_id == account.id, Alert.status != ALERT_RESOLVED)
        .order_by(Alert.date.desc()).limit(10).all()
    )
    from . import actions as act_svc
    recent_actions = act_svc.recent(account.id)

    return {
        "account": account,
        "row": row,
        "hero": row["cur"],
        "prev": row["prev"],
        "daily": daily,
        "cat": summary,
        "funnel": funnel,
        "agg": agg,
        "period": (start, end),
        "prior": (p_start, p_end),
        "alerts": active_alerts,
        "actions": recent_actions,
        "measurement": account.measurement,
    }
