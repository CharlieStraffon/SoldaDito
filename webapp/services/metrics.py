"""Métricas operativas del periodo (del sync diario), para el centro de control.

Columna vertebral (matriz §3): resultado · costo/resultado · inversión · ROAS · Δ vs normal.
  · resultado = Σ conversions (valor del objetivo primario; en Meta messaging = mensajes).
  · ROAS solo donde el valor es REAL (ecommerce o value_source=auto_platform); en leads
    manual_close el valor de plataforma es proxy de Smart Bidding -> se oculta.
Plataformas nunca se suman: el tablero separa Google y Meta.
"""
from datetime import timedelta

from sqlalchemy import func

from ..constants import PANEL_ECOMMERCE, VALUE_AUTO_PLATFORM
from ..database import db
from ..models import Account, Campaign, CampaignMetric
from . import categorization as cat

_SUM_FIELDS = (
    "impressions", "clicks", "cost", "conversions", "conversion_value",
    "reach", "link_clicks", "messages", "purchases", "purchases_value",
    "leads", "leads_value", "add_to_cart", "initiate_checkout", "add_payment_info",
)


def latest_metric_date():
    return db.session.query(func.max(CampaignMetric.date)).scalar()


def aggregate_by_account(start, end):
    """{account_id: {campo: suma}} para [start, end] (una sola consulta agregada)."""
    cols = [Campaign.account_id] + [func.coalesce(func.sum(getattr(CampaignMetric, f)), 0).label(f)
                                    for f in _SUM_FIELDS]
    q = (
        db.session.query(*cols)
        .join(Campaign, Campaign.id == CampaignMetric.campaign_id)
        .filter(CampaignMetric.date >= start, CampaignMetric.date <= end)
        .group_by(Campaign.account_id)
    )
    out = {}
    for row in q.all():
        d = {f: (getattr(row, f) or 0) for f in _SUM_FIELDS}
        out[row.account_id] = d
    return out


def aggregate_account(account_id, start, end):
    return aggregate_by_account(start, end).get(account_id)


def account_daily(account_id, start, end):
    """Serie diaria (para gráfica): cost, conversions, conversion_value por día."""
    q = (
        db.session.query(
            CampaignMetric.date,
            func.coalesce(func.sum(CampaignMetric.cost), 0),
            func.coalesce(func.sum(CampaignMetric.conversions), 0),
            func.coalesce(func.sum(CampaignMetric.conversion_value), 0),
        )
        .join(Campaign, Campaign.id == CampaignMetric.campaign_id)
        .filter(Campaign.account_id == account_id)
        .filter(CampaignMetric.date >= start, CampaignMetric.date <= end)
        .group_by(CampaignMetric.date)
        .order_by(CampaignMetric.date)
    )
    return [{"date": d.isoformat(), "cost": float(c), "conversions": float(cv), "value": float(val)}
            for d, c, cv, val in q.all()]


def _has_real_value(account):
    return cat.panel_of(account) == PANEL_ECOMMERCE or account.value_source == VALUE_AUTO_PLATFORM


def hero(account, agg):
    """Métricas héroe de una cuenta para el resumen ejecutivo."""
    agg = agg or {f: 0 for f in _SUM_FIELDS}
    inversion = agg["cost"]
    resultado = agg["conversions"]
    costo_resultado = (inversion / resultado) if resultado else None
    roas = (agg["conversion_value"] / inversion) if (inversion and _has_real_value(account)) else None
    return {
        "inversion": inversion,
        "resultado": resultado,
        "costo_resultado": costo_resultado,
        "roas": roas,
        "conversion_value": agg["conversion_value"] if _has_real_value(account) else None,
        "clicks": agg["clicks"],
        "impressions": agg["impressions"],
        "result_label": cat.result_label(account),
        "cost_label": cat.cost_label(account),
        "has_real_value": _has_real_value(account),
    }


def _delta_pct(cur, prev):
    if cur is None or prev in (None, 0):
        return None
    return (cur - prev) / prev * 100.0


def concern_score(account, cur, prev):
    """Mayor = peor (para ordenar peor-primero)."""
    panel = cat.panel_of(account)
    # Silenciada: gastaba antes, ahora cero.
    if cur["inversion"] == 0 and prev["inversion"] > 0:
        return 10_000.0
    if cur["inversion"] == 0:
        return -1e9  # sin actividad -> al fondo
    if panel == PANEL_ECOMMERCE and cur["roas"] is not None:
        d = _delta_pct(cur["roas"], prev["roas"])
        return -(d if d is not None else 0)        # ROAS cae -> concern sube
    d = _delta_pct(cur["costo_resultado"], prev["costo_resultado"])
    return d if d is not None else 0               # costo/resultado sube -> concern


def account_row(account, cur_agg, prev_agg):
    """Fila del resumen ejecutivo: héroe + delta vs periodo anterior + bandera."""
    cur = hero(account, cur_agg)
    prev = hero(account, prev_agg)
    panel = cat.panel_of(account)
    hero_metric = "roas" if (panel == PANEL_ECOMMERCE and cur["roas"] is not None) else "costo_resultado"
    delta = _delta_pct(cur[hero_metric], prev[hero_metric])
    silent = cur["inversion"] == 0 and prev["inversion"] > 0
    # Adverso: ROAS bajando o costo/resultado subiendo.
    adverse = False
    if delta is not None:
        adverse = (delta < 0) if hero_metric == "roas" else (delta > 0)
    return {
        "account": account,
        "cur": cur,
        "prev": prev,
        "hero_metric": hero_metric,
        "delta_pct": delta,
        "adverse": adverse,
        "silent": silent,
        "concern": concern_score(account, cur, prev),
        "panel": panel,
    }


def prior_period(start, end):
    length = (end - start).days + 1
    p_end = start - timedelta(days=1)
    p_start = p_end - timedelta(days=length - 1)
    return p_start, p_end
