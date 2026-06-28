"""Arma el resumen ejecutivo del centro de control.

Reglas: separado por plataforma (nunca se suman), peor-primero, sin totales de agencia,
señal por cuenta. Pendientes de clasificar se listan aparte (administración).
"""
from ..constants import PLATFORMS, STATUS_PENDIENTE
from ..models import Account
from . import metrics
from . import categorization as cat


def build_summary(start, end):
    p_start, p_end = metrics.prior_period(start, end)
    cur = metrics.aggregate_by_account(start, end)
    prev = metrics.aggregate_by_account(p_start, p_end)

    accounts = Account.query.filter(Account.is_active.is_(True)).all()
    by_platform = {p: [] for p in PLATFORMS}
    pending = []

    for a in accounts:
        if cat.is_pending(a):
            pending.append(a)
            continue
        row = metrics.account_row(a, cur.get(a.id), prev.get(a.id))
        by_platform.setdefault(a.platform, []).append(row)

    # Peor-primero por plataforma.
    for p in by_platform:
        by_platform[p].sort(key=lambda r: r["concern"], reverse=True)

    return {
        "by_platform": by_platform,
        "pending": pending,
        "prior": (p_start, p_end),
    }
