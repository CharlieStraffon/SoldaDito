"""Cliente Google Ads — PORT fiel del comportamiento probado del legacy.

Preserva:
  · Conversión de unidades: *_micros / 1_000_000 ; ctr * 100.
  · Enumeración de leaf accounts vía MCC (customer_client, manager=false).
  · conversion_category derivada de acciones primarias (sugerencia de seed).
  · Moneda por cuenta (customer.currency_code).
  · La ventana de re-escritura de 3 días vive en el servicio de sync, no aquí.

El SDK `google-ads` se importa de forma PEREZOSA.
"""
from datetime import date

from config import Config
from ..constants import PLATFORM_GOOGLE_ADS

MICROS = 1_000_000

# Categorías de conversión genéricas que NO cuentan para el panel.
_GENERIC_CATEGORIES = {"DEFAULT", "PAGE_VIEW", "ENGAGEMENT", "DOWNLOAD", "STORE_VISIT"}


def is_configured() -> bool:
    return Config.google_ads_configured()


def _client():
    """Inicializa el GoogleAdsClient perezosamente."""
    from google.ads.googleads.client import GoogleAdsClient
    cfg = {
        "developer_token": Config.GOOGLE_ADS_DEVELOPER_TOKEN,
        "client_id": Config.GOOGLE_ADS_CLIENT_ID,
        "client_secret": Config.GOOGLE_ADS_CLIENT_SECRET,
        "refresh_token": Config.GOOGLE_ADS_REFRESH_TOKEN,
        "use_proto_plus": True,
    }
    if Config.GOOGLE_ADS_LOGIN_CUSTOMER_ID:
        cfg["login_customer_id"] = Config.GOOGLE_ADS_LOGIN_CUSTOMER_ID.replace("-", "")
    return GoogleAdsClient.load_from_dict(cfg)


def get_ad_accounts():
    """Leaf accounts desde el MCC (customer_client). Devuelve roster normalizado."""
    client = _client()
    ga_service = client.get_service("GoogleAdsService")
    login_id = Config.GOOGLE_ADS_LOGIN_CUSTOMER_ID.replace("-", "")
    query = """
        SELECT customer_client.id, customer_client.descriptive_name,
               customer_client.currency_code, customer_client.manager,
               customer_client.status
        FROM customer_client
        WHERE customer_client.manager = false
    """
    out = []
    resp = ga_service.search(customer_id=login_id, query=query)
    for row in resp:
        cc = row.customer_client
        out.append({
            "external_account_id": str(cc.id),
            "name": cc.descriptive_name,
            "currency": cc.currency_code or "MXN",
            "account_status": cc.status.name if hasattr(cc.status, "name") else str(cc.status),
            "platform": PLATFORM_GOOGLE_ADS,
        })
    return out


def get_metrics(external_account_id, start: date, end: date):
    """Métricas campaña-día normalizadas para [start, end]."""
    client = _client()
    ga_service = client.get_service("GoogleAdsService")
    query = f"""
        SELECT campaign.id, campaign.name, campaign.advertising_channel_type,
               campaign.status, campaign.bidding_strategy_type,
               campaign_budget.amount_micros,
               segments.date,
               metrics.impressions, metrics.clicks, metrics.cost_micros,
               metrics.ctr, metrics.conversions, metrics.conversions_value,
               metrics.conversions_from_interactions_rate,
               metrics.search_budget_lost_impression_share,
               metrics.search_rank_lost_impression_share
        FROM campaign
        WHERE segments.date BETWEEN '{start.isoformat()}' AND '{end.isoformat()}'
    """
    rows = []
    try:
        resp = ga_service.search(customer_id=str(external_account_id).replace("-", ""), query=query)
    except Exception as e:  # noqa
        err = str(e)
        if any(m in err for m in ("CUSTOMER_NOT_ENABLED", "PERMISSION_DENIED",
                                  "REQUESTED_METRICS_FOR_MANAGER")):
            return []
        raise
    for r in resp:
        c, m, seg = r.campaign, r.metrics, r.segments
        budget = getattr(r, "campaign_budget", None)
        rows.append({
            "external_account_id": str(external_account_id),
            "external_campaign_id": str(c.id),
            "campaign_name": c.name,
            "campaign_type": c.advertising_channel_type.name if hasattr(c.advertising_channel_type, "name") else str(c.advertising_channel_type),
            "status": c.status.name if hasattr(c.status, "name") else str(c.status),
            "bidding_strategy_type": c.bidding_strategy_type.name if hasattr(c.bidding_strategy_type, "name") else None,
            "daily_budget": (budget.amount_micros / MICROS) if budget and budget.amount_micros else None,
            "date": seg.date,
            "impressions": int(m.impressions or 0),
            "clicks": int(m.clicks or 0),
            "cost": (m.cost_micros or 0) / MICROS,
            "ctr": (m.ctr or 0) * 100,
            "conversions": float(m.conversions or 0),
            "conversion_value": float(m.conversions_value or 0),
            "conversion_rate": (m.conversions_from_interactions_rate or 0) * 100,
            "search_budget_lost_impression_share": float(m.search_budget_lost_impression_share or 0),
            "search_rank_lost_impression_share": float(m.search_rank_lost_impression_share or 0),
        })
    return rows


def derive_conversion_category(external_account_id):
    """Categoría dominante de las acciones primarias-para-goal (sugerencia de seed)."""
    client = _client()
    ga_service = client.get_service("GoogleAdsService")
    query = """
        SELECT conversion_action.category, conversion_action.status,
               conversion_action.primary_for_goal
        FROM conversion_action
        WHERE conversion_action.status = 'ENABLED'
    """
    tally = {}
    try:
        resp = ga_service.search(customer_id=str(external_account_id).replace("-", ""), query=query)
    except Exception:  # noqa
        return None
    for r in resp:
        cat = r.conversion_action.category.name if hasattr(r.conversion_action.category, "name") else str(r.conversion_action.category)
        if cat in _GENERIC_CATEGORIES:
            continue
        tally[cat] = tally.get(cat, 0) + 1
    if not tally:
        return None
    return max(tally, key=tally.get)
