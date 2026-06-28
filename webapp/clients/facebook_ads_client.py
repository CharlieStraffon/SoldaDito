"""Cliente Meta/Facebook Ads — PORT fiel del comportamiento probado del legacy.

Preserva:
  · Dedup de conversiones por ORDEN DE PRIORIDAD (no sumar variantes superpuestas).
  · Picking por objetivo (SALES->purchases, LEADS->leads, MESSAGING->messages).
  · Mapeo de campos y unidades (daily_budget en menor / 100; spend ya en mayor).
  · Enumeración Business Manager -> fallback me/adaccounts (dedup por id).
  · Moneda por cuenta (account.currency); jamás se mezcla.

El SDK `facebook_business` se importa de forma PEREZOSA: el app y los tests
levantan sin él instalado. Instalar con `requirements-sync.txt` para sync real.
"""
from datetime import date, timedelta

from config import Config
from ..constants import PLATFORM_FACEBOOK_ADS

API_VERSION = Config.FACEBOOK_ADS_API_VERSION

# --- Grupos de action types con prioridad (toma el PRIMERO disponible) ---
PURCHASE_ACTIONS = [
    "purchase",
    "omni_purchase",
    "offsite_conversion.fb_pixel_purchase",
    "onsite_web_purchase",
]
LEAD_ACTIONS = [
    "lead",
    "onsite_conversion.lead_grouped",
    "offsite_conversion.fb_pixel_lead",
    "complete_registration",
    "offsite_conversion.fb_pixel_complete_registration",
]
MESSAGING_ACTIONS = [
    "onsite_conversion.messaging_conversation_started_7d",
    "onsite_conversion.messaging_conversation_started",
]
ATC_ACTIONS = ["add_to_cart", "omni_add_to_cart", "offsite_conversion.fb_pixel_add_to_cart"]
IC_ACTIONS = ["initiate_checkout", "omni_initiated_checkout"]
API_ACTIONS = ["add_payment_info", "omni_add_payment_info"]

INSIGHT_FIELDS = [
    "account_id", "account_name", "campaign_id", "campaign_name", "objective",
    "impressions", "clicks", "spend", "ctr", "frequency", "reach",
    "inline_link_clicks", "unique_inline_link_clicks",
    "actions", "action_values", "video_thruplay_watched_actions", "date_start",
]


def is_configured() -> bool:
    return Config.facebook_ads_configured()


def _sdk():
    """Importa el SDK perezosamente y lo inicializa. Lanza si falta o no hay token."""
    from facebook_business.api import FacebookAdsApi  # noqa
    FacebookAdsApi.init(
        app_id=Config.FACEBOOK_ADS_APP_ID,
        app_secret=Config.FACEBOOK_ADS_APP_SECRET,
        access_token=Config.FACEBOOK_ADS_ACCESS_TOKEN,
        api_version=API_VERSION,
    )
    return FacebookAdsApi


def _pick_first(action_map, names):
    """Dedup por prioridad: devuelve el valor del primer action type presente."""
    for n in names:
        if n in action_map:
            return float(action_map[n] or 0)
    return 0.0


def _classify_objective(objective):
    o = (objective or "").upper().replace("OUTCOME_", "")
    if o in ("SALES", "CONVERSIONS", "PRODUCT_CATALOG_SALES"):
        return "sales"
    if o in ("LEADS", "LEAD_GENERATION"):
        return "leads"
    if o in ("MESSAGES", "ENGAGEMENT", "MESSAGING"):
        return "messaging"
    return "other"


def normalize_insight(insight: dict) -> dict:
    """Convierte una fila de Insights de la API a la forma interna (campaña-día)."""
    actions = {a["action_type"]: a.get("value", 0) for a in (insight.get("actions") or [])}
    values = {a["action_type"]: a.get("value", 0) for a in (insight.get("action_values") or [])}

    purchases = _pick_first(actions, PURCHASE_ACTIONS)
    purchases_value = _pick_first(values, PURCHASE_ACTIONS)
    leads = _pick_first(actions, LEAD_ACTIONS)
    leads_value = _pick_first(values, LEAD_ACTIONS)
    messages = _pick_first(actions, MESSAGING_ACTIONS)
    add_to_cart = _pick_first(actions, ATC_ACTIONS)
    initiate_checkout = _pick_first(actions, IC_ACTIONS)
    add_payment_info = _pick_first(actions, API_ACTIONS)

    goal = _classify_objective(insight.get("objective"))
    if goal == "sales":
        conversions, conversion_value = purchases, purchases_value
    elif goal == "leads":
        conversions, conversion_value = leads, leads_value
    elif goal == "messaging":
        conversions, conversion_value = messages, 0.0      # mensajes no tienen valor monetario
    else:
        if purchases:
            conversions, conversion_value = purchases, purchases_value
        elif leads:
            conversions, conversion_value = leads, leads_value
        else:
            conversions, conversion_value = messages, 0.0

    thruplays = 0.0
    for tp in (insight.get("video_thruplay_watched_actions") or []):
        thruplays += float(tp.get("value", 0) or 0)

    return {
        "external_account_id": _norm_account_id(insight.get("account_id")),
        "account_name": insight.get("account_name"),
        "external_campaign_id": insight.get("campaign_id"),
        "campaign_name": insight.get("campaign_name"),
        "campaign_type": (insight.get("objective") or "").replace("OUTCOME_", ""),
        "date": insight.get("date_start"),
        "impressions": int(float(insight.get("impressions", 0) or 0)),
        "clicks": int(float(insight.get("clicks", 0) or 0)),
        "cost": float(insight.get("spend", 0) or 0),
        "ctr": float(insight.get("ctr", 0) or 0),
        "frequency": float(insight.get("frequency", 0) or 0),
        "reach": int(float(insight.get("reach", 0) or 0)),
        "link_clicks": float(insight.get("inline_link_clicks", 0) or 0),
        "unique_link_clicks": float(insight.get("unique_inline_link_clicks", 0) or 0),
        "thruplays": thruplays,
        "conversions": conversions,
        "conversion_value": conversion_value,
        "purchases": purchases,
        "purchases_value": purchases_value,
        "leads": leads,
        "leads_value": leads_value,
        "messages": messages,
        "add_to_cart": add_to_cart,
        "initiate_checkout": initiate_checkout,
        "add_payment_info": add_payment_info,
    }


def _norm_account_id(acct_id):
    if not acct_id:
        return acct_id
    s = str(acct_id)
    return s if s.startswith("act_") else f"act_{s}"


def get_ad_accounts():
    """Roster de cuentas de Meta. Business Manager -> fallback me/adaccounts (dedup)."""
    _sdk()
    from facebook_business.adobjects.business import Business
    from facebook_business.adobjects.user import User

    fields = ["id", "account_id", "name", "currency", "account_status"]
    seen, out = set(), []

    def _add(acct):
        ext = _norm_account_id(acct.get("account_id") or acct.get("id"))
        if not ext or ext in seen:
            return
        seen.add(ext)
        out.append({
            "external_account_id": ext,
            "name": acct.get("name"),
            "currency": acct.get("currency") or "MXN",
            "account_status": _status_label(acct.get("account_status")),
            "platform": PLATFORM_FACEBOOK_ADS,
        })

    if Config.FACEBOOK_ADS_BUSINESS_ID:
        try:
            biz = Business(Config.FACEBOOK_ADS_BUSINESS_ID)
            for a in biz.get_owned_ad_accounts(fields=fields):
                _add(dict(a))
            for a in biz.get_client_ad_accounts(fields=fields):
                _add(dict(a))
        except Exception as e:  # noqa
            print(f"[facebook] business enumeration failed: {e}")

    if not out:
        me = User(fbid="me")
        for a in me.get_ad_accounts(fields=fields):
            _add(dict(a))
    return out


_FB_STATUS = {1: "ACTIVE", 2: "DISABLED", 3: "UNSETTLED", 7: "PENDING_RISK_REVIEW",
              8: "PENDING_SETTLEMENT", 9: "IN_GRACE_PERIOD", 100: "PENDING_CLOSURE",
              101: "CLOSED", 201: "ANY_ACTIVE", 202: "ANY_CLOSED"}


def _status_label(code):
    try:
        return _FB_STATUS.get(int(code), str(code))
    except (TypeError, ValueError):
        return str(code) if code is not None else None


def get_insights(external_account_id, start: date, end: date):
    """Insights campaña-día normalizados, para [start, end]."""
    _sdk()
    from facebook_business.adobjects.adaccount import AdAccount

    acct = AdAccount(_norm_account_id(external_account_id))
    params = {
        "level": "campaign",
        "time_range": {"since": start.isoformat(), "until": end.isoformat()},
        "time_increment": 1,
        "limit": 500,
    }
    rows = []
    try:
        for ins in acct.get_insights(fields=INSIGHT_FIELDS, params=params):
            rows.append(normalize_insight(dict(ins)))
    except Exception as e:  # noqa
        msg = str(e).lower()
        if "does not support the #insights" in msg:
            return []
        print(f"[facebook] insights failed for {external_account_id}: {e}")
        return []
    return rows


def derive_conversion_category(external_account_id):
    """Sugerencia de panel_type para el seed (objetivo dominante). NO fuente en runtime."""
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=30)
    rows = get_insights(external_account_id, start, end)
    tally = {"sales": 0.0, "leads": 0.0, "messaging": 0.0}
    for r in rows:
        if r["purchases"]:
            tally["sales"] += r["purchases"]
        if r["leads"]:
            tally["leads"] += r["leads"]
        if r["messages"]:
            tally["messaging"] += r["messages"]
    if not any(tally.values()):
        return None
    best = max(tally, key=tally.get)
    return {"sales": "PURCHASE", "leads": "LEAD", "messaging": "MESSAGING"}[best]
