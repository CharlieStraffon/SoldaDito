"""Desglose mensual (cuenta-mes) + cierre de mes.

· Campos API (inversión, clics, embudo, y para ecommerce ventas/monto) se refrescan
  del sync mientras el mes está ABIERTO.
· Campos MANUAL (leads: ventas_concretadas/monto; ventas_totales) los captura el equipo.
· Calculados via motor financiero canónico (finance.compute_account_month).
· Cierre (por engagement): congela margin_pct_snapshot + fee_snapshot, bloquea edición,
  y alimenta AccountBaseline ("tu normal").
"""
import calendar
from datetime import date, datetime

from sqlalchemy import func

from ..constants import PANEL_ECOMMERCE, VALUE_AUTO_PLATFORM
from ..database import db
from ..models import Campaign, CampaignMetric, MonthlyHistory
from . import categorization as cat
from . import engagement as eng
from . import finance


def month_bounds(year, month):
    last = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def api_aggregate(account, year, month):
    start, end = month_bounds(year, month)
    fields = ["cost", "clicks", "conversions", "conversion_value", "purchases",
              "purchases_value", "add_to_cart", "initiate_checkout"]
    cols = [func.coalesce(func.sum(getattr(CampaignMetric, f)), 0) for f in fields]
    row = (
        db.session.query(*cols)
        .join(Campaign, Campaign.id == CampaignMetric.campaign_id)
        .filter(Campaign.account_id == account.id)
        .filter(CampaignMetric.date >= start, CampaignMetric.date <= end)
        .first()
    )
    return dict(zip(fields, [float(v or 0) for v in row])) if row else {f: 0.0 for f in fields}


def get_or_build(account, year, month, refresh_api=True):
    """Devuelve la fila cuenta-mes, refrescando API si está abierta. Recalcula."""
    row = MonthlyHistory.query.filter_by(account_id=account.id, year=year, month=month).first()
    if row is None:
        row = MonthlyHistory(account_id=account.id, year=year, month=month,
                             platform=account.platform, client_id=account.client_id,
                             currency=account.currency)
        db.session.add(row)
        row.panel_type_snapshot = cat.panel_of(account)

    panel = cat.panel_of(account)
    auto_value = panel == PANEL_ECOMMERCE or account.value_source == VALUE_AUTO_PLATFORM

    if refresh_api and not row.is_closed:
        agg = api_aggregate(account, year, month)
        row.inversion = agg["cost"]
        row.inversion_source = "api"
        row.clics = agg["clicks"]
        row.add_to_carts = agg["add_to_cart"]
        row.checkouts = agg["initiate_checkout"]
        if panel == PANEL_ECOMMERCE:
            row.ventas = agg["purchases"] or agg["conversions"]
            row.monto_venta = agg["purchases_value"] or agg["conversion_value"]
            row.ventas_source = row.monto_source = "api"
        else:
            row.prospectos = agg["conversions"]  # leads: resultado primario (API)
            if auto_value:  # Ser Rizada: valor real on-site
                row.ventas = agg["conversions"]
                row.monto_venta = agg["conversion_value"]
                row.ventas_source = row.monto_source = "api"

    recompute(account, row)
    db.session.commit()
    return row


def recompute(account, row):
    panel = cat.panel_of(account)
    margin = row.margin_pct_snapshot if row.is_closed and row.margin_pct_snapshot is not None \
        else (account.client.effective_margin() if account.client else None)
    base_conv = "clics" if panel == PANEL_ECOMMERCE else "prospectos"
    cm = finance.compute_account_month(
        inversion=row.inversion,
        prospectos=row.prospectos,
        clics=row.clics,
        ventas=row.ventas,
        monto=row.monto_venta,
        margin_pct=margin,
        purpose=account.purpose,
        value_source=account.value_source,
        base_conv=base_conv,
    )
    row.cpl = cm["cpl"]
    row.cpa = cm["cpa"]
    row.roas = cm["roas"]
    row.aov = cm["aov"]
    row.conv_pct = cm["conv_pct"]
    row.cpv = cm["cpv"]
    row.utilidad_antes_honorarios = cm["utilidad_antes_honorarios"]


def save_manual(account, year, month, data):
    """Captura manual (leads). Bloqueada si el mes está cerrado."""
    row = get_or_build(account, year, month, refresh_api=False)
    if row.is_closed:
        return row, "El mes está cerrado: no se puede editar."
    for field in ("ventas", "monto_venta", "prospectos", "ventas_totales"):
        if field in data and data[field] not in (None, ""):
            setattr(row, field, float(data[field]))
            if field in ("ventas", "monto_venta"):
                setattr(row, field.split("_")[0] + "_source" if field == "ventas" else "monto_source", "manual")
    if data.get("ventas") not in (None, ""):
        row.ventas_source = "manual"
    if data.get("monto_venta") not in (None, ""):
        row.monto_source = "manual"
    if "notes" in data:
        row.notes = data["notes"]
    recompute(account, row)
    db.session.commit()
    return row, None


def close_engagement(client, platform, year, month):
    """Cierra el mes de un engagement: congela snapshots, bloquea edición, alimenta baseline."""
    accounts = eng.engagement_accounts(client.id, platform)
    honorarios = eng.resolve_honorarios(accounts)
    margin = client.effective_margin()
    closed = 0
    for a in accounts:
        row = get_or_build(a, year, month, refresh_api=True)
        row.margin_pct_snapshot = margin
        row.fee_snapshot = honorarios
        row.is_closed = True
        row.closed_at = datetime.utcnow()
        closed += 1
    db.session.commit()
    # Alimenta "tu normal" (F5). Import perezoso para evitar ciclos.
    try:
        from . import baseline
        for a in accounts:
            baseline.recompute_account(a)
    except Exception:  # noqa
        pass
    return closed


def breakdown(client, platform, year, month):
    """Ensambla la vista de desglose de un engagement-mes (filas + KPIs + referencias)."""
    accounts = eng.engagement_accounts(client.id, platform)
    rows = [(a, get_or_build(a, year, month)) for a in accounts]
    eng_metrics = eng.compute_month(client, platform, year, month)
    # Referencias: tu normal (baseline) + objetivo (target) por cuenta.
    from ..models import AccountBaseline, MonthlyTarget
    refs = {}
    for a in accounts:
        bl = {b.metric: b for b in AccountBaseline.query.filter_by(account_id=a.id, window_days=90).all()}
        tg = {t.metric: t for t in MonthlyTarget.query.filter_by(account_id=a.id, year=year, month=month).all()}
        refs[a.id] = {"normal": bl, "target": tg}
    is_closed = any(r.is_closed for _, r in rows)
    return {
        "client": client, "platform": platform, "year": year, "month": month,
        "rows": rows, "engagement": eng_metrics, "refs": refs, "is_closed": is_closed,
    }


def reopen_engagement(client, platform, year, month):
    accounts = eng.engagement_accounts(client.id, platform)
    for a in accounts:
        row = MonthlyHistory.query.filter_by(account_id=a.id, year=year, month=month).first()
        if row:
            row.is_closed = False
            row.closed_at = None
    db.session.commit()
