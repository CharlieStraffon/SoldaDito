"""Servicio de sync — upsert idempotente + ventana de re-escritura de 3 días.

PORT del comportamiento probado:
  · Upsert por clave estable: Account(platform,ext_id), Campaign(platform,ext_id),
    CampaignMetric(campaign_id, date).
  · Catch-up: re-jala SIEMPRE los últimos GOOGLE_CATCHUP_REFRESH_DAYS y rellena
    gaps hasta CATCHUP_MAX_GAP_DAYS (atribución tardía de Google).
  · Backfill en chunks de BACKFILL_CHUNK_DAYS.
  · Commits por lotes de 500.
  · Moneda por cuenta desde la API; nunca se mezcla.
"""
from datetime import date, timedelta

from ..constants import (
    BACKFILL_CHUNK_DAYS,
    CATCHUP_MAX_GAP_DAYS,
    GOOGLE_CATCHUP_REFRESH_DAYS,
    PLATFORM_FACEBOOK_ADS,
    PLATFORM_GOOGLE_ADS,
)
from ..database import db
from ..models import Account, Campaign, CampaignMetric

_BATCH = 500


# --------------------------------------------------------------------------- #
# Roster
# --------------------------------------------------------------------------- #
def fetch_roster(platform):
    """Roster en vivo desde la API (lista de dicts normalizados)."""
    if platform == PLATFORM_GOOGLE_ADS:
        from ..clients import google_ads_client as g
        return g.get_ad_accounts() if g.is_configured() else []
    if platform == PLATFORM_FACEBOOK_ADS:
        from ..clients import facebook_ads_client as f
        return f.get_ad_accounts() if f.is_configured() else []
    return []


def upsert_account_from_roster(row):
    """Crea/actualiza Account con datos de API. NO toca campos de seed/edición."""
    ext = row["external_account_id"]
    platform = row["platform"]
    acct = Account.query.filter_by(platform=platform, external_account_id=ext).first()
    if acct is None:
        acct = Account(platform=platform, external_account_id=ext)
        db.session.add(acct)
    # Campos API (read-only desde la app): siempre se re-estampan.
    acct.name = row.get("name") or acct.name
    acct.currency = row.get("currency") or acct.currency
    acct.account_status = row.get("account_status") or acct.account_status
    return acct


# --------------------------------------------------------------------------- #
# Catch-up / backfill
# --------------------------------------------------------------------------- #
def _existing_dates(account_id, start, end):
    q = (
        db.session.query(CampaignMetric.date)
        .join(Campaign, Campaign.id == CampaignMetric.campaign_id)
        .filter(Campaign.account_id == account_id)
        .filter(CampaignMetric.date >= start, CampaignMetric.date <= end)
        .distinct()
    )
    return {d[0] for d in q.all()}


def catchup_window(account_id, today=None):
    """Calcula [start, end] del catch-up: últimos 3 días + gaps hasta 30 días.

    end = ayer. refresh_start = end - (REFRESH_DAYS-1). Busca el primer día
    faltante en [end-30, end]; start = min(faltante, refresh_start).
    """
    today = today or date.today()
    end = today - timedelta(days=1)
    refresh_start = end - timedelta(days=GOOGLE_CATCHUP_REFRESH_DAYS - 1)
    look_back_start = end - timedelta(days=CATCHUP_MAX_GAP_DAYS)

    have = _existing_dates(account_id, look_back_start, end)
    earliest_missing = None
    d = look_back_start
    while d <= end:
        if d not in have:
            earliest_missing = d
            break
        d += timedelta(days=1)

    start = refresh_start if earliest_missing is None else min(earliest_missing, refresh_start)
    return start, end


def _upsert_campaign(account, row):
    ext = row["external_campaign_id"]
    camp = Campaign.query.filter_by(
        platform=account.platform, external_campaign_id=ext
    ).first()
    if camp is None:
        camp = Campaign(platform=account.platform, external_campaign_id=ext, account_id=account.id)
        db.session.add(camp)
        db.session.flush()
    camp.account_id = account.id
    camp.name = row.get("campaign_name") or camp.name
    camp.campaign_type = row.get("campaign_type") or camp.campaign_type
    camp.status = row.get("status") or camp.status
    if row.get("bidding_strategy_type") is not None:
        camp.bidding_strategy_type = row["bidding_strategy_type"]
    if row.get("daily_budget") is not None:
        camp.daily_budget = row["daily_budget"]
    return camp


_METRIC_FIELDS = (
    "impressions", "clicks", "cost", "conversions", "conversion_value", "ctr",
    "conversion_rate", "reach", "frequency", "link_clicks", "unique_link_clicks",
    "thruplays", "purchases", "purchases_value", "leads", "leads_value",
    "messages", "add_to_cart", "initiate_checkout", "add_payment_info",
    "search_budget_lost_impression_share", "search_rank_lost_impression_share",
)


def _upsert_metric(platform, campaign_id, row):
    row_date = row["date"]
    if isinstance(row_date, str):
        row_date = date.fromisoformat(row_date)
    metric = CampaignMetric.query.filter_by(campaign_id=campaign_id, date=row_date).first()
    if metric is None:
        metric = CampaignMetric(campaign_id=campaign_id, date=row_date, platform=platform)
        db.session.add(metric)
    metric.platform = platform  # re-estampa (corrección de atribución tardía)
    for f in _METRIC_FIELDS:
        if f in row and row[f] is not None:
            setattr(metric, f, row[f])


def _pull_metrics(account, start, end):
    if account.platform == PLATFORM_GOOGLE_ADS:
        from ..clients import google_ads_client as g
        return g.get_metrics(account.external_account_id, start, end)
    from ..clients import facebook_ads_client as f
    return f.get_insights(account.external_account_id, start, end)


def sync_account(account, start, end):
    """Jala métricas [start,end] en chunks y upsertea. Devuelve conteo."""
    n = 0
    chunk_start = start
    while chunk_start <= end:
        chunk_end = min(chunk_start + timedelta(days=BACKFILL_CHUNK_DAYS - 1), end)
        rows = _pull_metrics(account, chunk_start, chunk_end)
        batch = 0
        for row in rows:
            camp = _upsert_campaign(account, row)
            _upsert_metric(account.platform, camp.id, row)
            n += 1
            batch += 1
            if batch >= _BATCH:
                db.session.commit()
                batch = 0
        db.session.commit()
        chunk_start = chunk_end + timedelta(days=1)
    return n


def run_catchup(platform):
    """Catch-up de todas las cuentas activas de una plataforma."""
    accounts = Account.query.filter_by(platform=platform, is_active=True).all()
    total = 0
    for acct in accounts:
        start, end = catchup_window(acct.id)
        total += sync_account(acct, start, end)
    return total
