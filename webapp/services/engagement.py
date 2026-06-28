"""Rollup engagement = cliente × plataforma sobre MonthlyHistory.

CRÍTICO (ADR-002 §5.1): el fee se cuenta UNA vez por engagement. Multi-Encomiendas
tiene 4 cuentas en Meta con el mismo fee — sumar account.monthly_fee lo cuadruplicaría.
Por eso honorarios = el fee del engagement (un solo valor), no la suma de cuentas.

Plataformas NUNCA se suman: cada (cliente, plataforma) es un número separado, en su moneda.
"""
from collections import defaultdict

from ..models import Account, MonthlyHistory
from . import finance


def resolve_honorarios(accounts):
    """Fee único del engagement. Las cuentas de un mismo (cliente,plataforma)
    comparten fee (de STATUS); tomamos el valor (max no-nulo), no la suma."""
    fees = [a.monthly_fee for a in accounts if a.monthly_fee is not None]
    return max(fees) if fees else 0.0


def engagement_accounts(client_id, platform):
    return Account.query.filter_by(client_id=client_id, platform=platform).all()


def list_engagements(only_active=True):
    """Agrupa cuentas por (client_id, platform). Devuelve lista de grupos."""
    q = Account.query.filter(Account.client_id.isnot(None))
    if only_active:
        q = q.filter(Account.is_active.is_(True))
    groups = defaultdict(list)
    for a in q.all():
        groups[(a.client_id, a.platform)].append(a)
    return groups


def compute_month(client, platform, year, month, ventas_totales=None):
    """Métricas engagement-mes para (cliente, plataforma, periodo)."""
    accounts = engagement_accounts(client.id, platform)
    acct_ids = [a.id for a in accounts]
    if not acct_ids:
        return None
    rows = MonthlyHistory.query.filter(
        MonthlyHistory.account_id.in_(acct_ids),
        MonthlyHistory.year == year,
        MonthlyHistory.month == month,
    ).all()
    honorarios = resolve_honorarios(accounts)
    # Snapshot de margen/fee si el mes está cerrado (usa el congelado de la 1a fila).
    closed_row = next((r for r in rows if r.is_closed), None)
    margin = (closed_row.margin_pct_snapshot if closed_row and closed_row.margin_pct_snapshot
              is not None else client.effective_margin())
    if closed_row and closed_row.fee_snapshot is not None:
        honorarios = closed_row.fee_snapshot

    eng = finance.compute_engagement_from_rows(
        rows, margin_pct=margin, honorarios=honorarios, ventas_totales=ventas_totales
    )
    eng.update({
        "client_id": client.id,
        "platform": platform,
        "year": year,
        "month": month,
        "currency": accounts[0].currency,
        "n_accounts": len(accounts),
        "is_closed": bool(closed_row),
        "n_rows": len(rows),
    })
    return eng
