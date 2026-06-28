"""'Tu normal' — AccountBaseline por cuenta × métrica.

Guarda el valor normal (MEDIANA, robusta a varianza alta) y la DISPERSIÓN (IQR),
en ventanas de 30 y 90 días — para mostrar Δ vs normal y para el z-score de Meta.

Nota: ADR §6 define el baseline ideal como mediana de MESES CERRADOS. Como la
detección diaria necesita una referencia diaria desde el día 1, calculamos el
normal sobre la serie diaria del sync (ventana móvil). Se recalcula al cerrar mes.
"""
import statistics
from datetime import timedelta

from sqlalchemy import func

from ..constants import PANEL_ECOMMERCE, VALUE_AUTO_PLATFORM
from ..database import db
from ..models import AccountBaseline, Campaign, CampaignMetric
from . import categorization as cat

WINDOWS = (30, 90)
# Métricas con baseline. cost_per_result aplica a ambos paneles (CPA/CPL).
BASE_METRICS = ("cost_per_result", "roas", "spend", "conversions")


def _daily_series(account_id, start, end):
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
    )
    return [(d, float(c), float(cv), float(val)) for d, c, cv, val in q.all()]


def _iqr(values):
    if len(values) < 4:
        return statistics.pstdev(values) if len(values) > 1 else 0.0
    s = sorted(values)
    n = len(s)
    q1 = s[n // 4]
    q3 = s[(3 * n) // 4]
    return q3 - q1


def _metric_values(series, metric, has_real_value):
    out = []
    for _, cost, conv, val in series:
        if cost <= 0:
            continue
        if metric == "spend":
            out.append(cost)
        elif metric == "conversions":
            out.append(conv)
        elif metric == "cost_per_result" and conv > 0:
            out.append(cost / conv)
        elif metric == "roas" and has_real_value:
            out.append(val / cost)
    return out


def recompute_account(account, as_of=None):
    """Recalcula AccountBaseline (mediana + IQR) en 30/90 días. Devuelve nº de filas."""
    as_of = as_of or db.session.query(func.max(CampaignMetric.date)).scalar()
    if as_of is None:
        return 0
    has_real = cat.panel_of(account) == PANEL_ECOMMERCE or account.value_source == VALUE_AUTO_PLATFORM
    n = 0
    for window in WINDOWS:
        start = as_of - timedelta(days=window - 1)
        series = _daily_series(account.id, start, as_of)
        for metric in BASE_METRICS:
            vals = _metric_values(series, metric, has_real)
            if len(vals) < 3:
                continue
            normal = statistics.median(vals)
            disp = _iqr(vals)
            bl = AccountBaseline.query.filter_by(
                account_id=account.id, metric=metric, window_days=window
            ).first()
            if bl is None:
                bl = AccountBaseline(account_id=account.id, metric=metric, window_days=window)
                db.session.add(bl)
            bl.platform = account.platform
            bl.normal_value = normal
            bl.dispersion = disp
            bl.sample_size = len(vals)
            bl.last_closed_period = f"{as_of.year}-{as_of.month:02d}"
            n += 1
    db.session.commit()
    return n


def get(account_id, metric, window=90):
    return AccountBaseline.query.filter_by(
        account_id=account_id, metric=metric, window_days=window
    ).first()


def recompute_all(as_of=None):
    from ..models import Account
    total = 0
    for a in Account.query.filter_by(is_active=True).all():
        total += recompute_account(a, as_of)
    return total
