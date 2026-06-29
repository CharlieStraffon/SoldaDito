"""Detalle de cuenta — contexto `d` para la página de marca (panel por tipo).

Tipo de panel visual:
  · ecommerce  -> hero ROAS + embudo
  · mensajes   -> hero costo/conversación + banda de frecuencia
  · leads      -> hero costo/lead + calidad del lead
Reusa metrics (periodo), baseline ("tu normal"), categorization, alerts.
"""
import calendar
from datetime import date

from ..constants import (
    ALERT_RESOLVED,
    CAPTURE_MESSAGES,
    PANEL_ECOMMERCE,
    PLATFORM_GOOGLE_ADS,
)
from ..models import Alert, Campaign, CampaignMetric, MonthlyHistory
from . import baseline
from . import categorization as cat
from . import metrics
from . import periods


def _money(v):
    return f"${v:,.0f}" if v is not None else "—"


def _ratio(v):
    return f"{v:.1f}x" if v is not None else "—"


def _pct(v):
    return f"{v:.1f}%" if v is not None else "—"


def visual_type(account):
    """ecommerce / mensajes / leads para escoger el panel (honra override)."""
    return cat.visual_type(account)


def _objetivo_tag(vtype):
    return {
        "ecommerce": ("ventas y ROAS", "ecommerce"),
        "mensajes": ("alcance y conversaciones", "mensajes"),
        "leads": ("CPL y calidad del lead", "leads"),
    }[vtype]


def build(account, start, end, period_key="30d"):
    vtype = visual_type(account)
    agg = metrics.aggregate_account(account.id, start, end) or {}
    p_s, p_e = metrics.prior_period(start, end)
    prev = metrics.aggregate_account(account.id, p_s, p_e) or {}
    h = metrics.hero(account, agg)
    hprev = metrics.hero(account, prev)
    period_label = periods.label_for(period_key, start, end)

    dot = _dot(account, h, hprev)
    plat_label = "Google Ads" if account.platform == PLATFORM_GOOGLE_ADS else "Facebook Ads"
    obj_label, obj_cls = _objetivo_tag(vtype)

    d = {
        "account": account,
        "platform": account.platform,
        "client_type": vtype,
        "period": period_key,
        "period_label": period_label,
        "presets": periods.PRESET_ITEMS,
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "header": {
            "name": account.name, "dot": dot,
            "meta": f"{cat.panel_of(account) or 'pendiente'} · {plat_label} · {period_label}",
            "type": obj_cls, "type_label": f"objetivo: {obj_label}",
        },
        "hero": _hero(account, vtype, h),
        "secondary": _secondary(account, vtype, agg, h),
        "ai": _ai(account),
        "funnel": _funnel(agg) if vtype == "ecommerce" else None,
        "freqband": _freqband(account, start, end) if vtype == "mensajes" else None,
        "quality": _quality(account) if vtype == "leads" else None,
        "camp_cols": _camp_cols(vtype),
        "camp_rows": _camp_rows(account, start, end, vtype, h),
        "daily": _daily(account, start, end, vtype, h),
    }
    return d


# --------------------------------------------------------------------------- #
def _dot(account, h, hprev):
    active = (Alert.query.filter(Alert.account_id == account.id, Alert.status != ALERT_RESOLVED).all())
    sev = {a.severity for a in active}
    if "critico" in sev or (h["inversion"] == 0):
        return "crit" if "critico" in sev else "idle"
    if "rendimiento" in sev:
        return "warn"
    return "ok"


def _hero(account, vtype, h):
    bl_metric = "roas" if vtype == "ecommerce" else "cost_per_result"
    bl = baseline.get(account.id, bl_metric, 90)
    normal = bl.normal_value if bl else None
    if vtype == "ecommerce":
        v = h["roas"]
        good = v is not None and (account.target_roas is None or v >= account.target_roas) and (normal is None or v >= normal)
        verdict_good = normal is None or (v is not None and v >= normal)
        return {
            "label": "ROAS", "value": _ratio(v), "good": good,
            "normal": _ratio(normal) if normal else None,
            "target": _ratio(account.target_roas) if account.target_roas else None,
            "freq": None, "freq_bad": False,
            "verdict": {"good": verdict_good, "text": ("▲ sobre tu normal" if verdict_good else "▼ bajo tu normal")},
            "vtext": (f"Por cada $1 invertido regresan {v:.1f}." if v else "Sin valor en el período."),
        }
    # leads / mensajes -> costo por resultado (menos es mejor)
    v = h["costo_resultado"]
    label = "COSTO POR MENSAJE" if vtype == "mensajes" else "COSTO POR LEAD"
    target = account.target_cpa
    under_target = v is not None and target and v <= target
    under_normal = v is not None and normal and v <= normal
    good = bool(under_target or under_normal)
    return {
        "label": label, "value": _money(v), "good": good,
        "normal": _money(normal) if normal else None,
        "target": _money(target) if target else None,
        "freq": None, "freq_bad": False,
        "verdict": {"good": good,
                    "text": ("▼ bajo el objetivo" if under_target else ("▼ bajo tu normal" if under_normal else "▲ sobre lo normal"))},
        "vtext": ("Cada resultado cuesta menos que el tope acordado." if under_target
                  else ("Cada resultado cuesta dentro de lo normal." if under_normal
                        else "El costo está por arriba de tu referencia.")),
    }


def _ctr(agg):
    imp, clk = agg.get("impressions", 0), agg.get("clicks", 0)
    return (clk / imp * 100) if imp else None


def _secondary(account, vtype, agg, h):
    bl = baseline.get(account.id, "cost_per_result", 90)
    ctr = _ctr(agg)
    ctr_bl = None
    if vtype == "ecommerce":
        return [
            {"l": "Inversión", "v": _money(h["inversion"]), "n": "período en curso"},
            {"l": "Ingresos", "v": _money(h["conversion_value"]), "n": "valor de ventas"},
            {"l": "CPA", "v": _money(h["costo_resultado"]), "n": (f"normal {_money(bl.normal_value)}" if bl else "")},
            {"l": "Ticket prom. (AOV)", "v": _money((h['conversion_value'] / h['resultado']) if h['resultado'] else None)},
            {"l": "Ventas", "v": f"{h['resultado']:,.0f}"},
            {"l": "CTR", "v": _pct(ctr), "n": ""},
        ]
    if vtype == "mensajes":
        return [
            {"l": "Inversión", "v": _money(h["inversion"]), "n": "período en curso"},
            {"l": "Conversaciones", "v": f"{h['resultado']:,.0f}"},
            {"l": "Costo/conversación", "v": _money(h["costo_resultado"]), "n": (f"normal {_money(bl.normal_value)}" if bl else "")},
            {"l": "CTR", "v": _pct(ctr)},
        ]
    # leads
    q = _quality(account)
    return [
        {"l": "Inversión", "v": _money(h["inversion"]), "n": "período en curso"},
        {"l": "Leads", "v": f"{h['resultado']:,.0f}"},
        {"l": "Calificados", "v": (f"{q['qualified']:,.0f}" if q else "—"), "n": ("" if q else "captura manual pendiente")},
        {"l": "% Calificación", "v": (_pct(q['pct']) if q else "—")},
        {"l": "Costo/lead calif.", "v": (_money(q['cost_per_qualified']) if q and q.get('cost_per_qualified') else "—")},
        {"l": "CTR", "v": _pct(ctr), "n": ""},
    ]


def _ai(account):
    a = (Alert.query.filter(Alert.account_id == account.id, Alert.status != ALERT_RESOLVED)
         .order_by(Alert.severity.desc()).first())
    if a:
        return a.ai_explanation or a.message
    return "Sin anomalías recientes. La cuenta opera dentro de su rango normal."


def _funnel(agg):
    imp = agg.get("impressions", 0)
    clk = agg.get("clicks", 0)
    atc = agg.get("add_to_cart", 0)
    chk = agg.get("initiate_checkout", 0)
    pur = agg.get("purchases", 0) or agg.get("conversions", 0)
    steps = [("Impresiones", imp, None, False), ("Clics", clk, imp, False),
             ("Add to cart", atc, clk, False), ("Checkout", chk, atc, False),
             ("Compra", pur, chk, True)]
    out, top = [], max(imp, 1)
    for label, val, base, last in steps:
        rate = (val / base * 100) if base else None
        out.append({"label": label, "value": f"{val:,.0f}",
                    "width": max(2, val / top * 100), "rate": (_pct(rate) if rate is not None else ""),
                    "is_last": last})
    return out


def _freqband(account, start, end):
    from sqlalchemy import func
    avg = (CampaignMetric.query
           .join(Campaign, Campaign.id == CampaignMetric.campaign_id)
           .filter(Campaign.account_id == account.id,
                   CampaignMetric.date >= start, CampaignMetric.date <= end)
           .with_entities(func.avg(CampaignMetric.frequency)).scalar())
    v = float(avg or 0)
    # marker on 0..6 scale across z1(2.5)/z2(1)/z3(1.5) = ~5 units
    marker = min(100, v / 6 * 100)
    return {"value": f"{v:.1f}", "marker": marker}


def _quality(account):
    a = periods.anchor_date()
    mh = MonthlyHistory.query.filter_by(account_id=account.id, year=a.year, month=a.month).first()
    if not mh or mh.ventas is None or not mh.prospectos:
        return None
    qualified = mh.ventas
    total = mh.prospectos
    pct = (qualified / total * 100) if total else None
    cpq = (mh.inversion / qualified) if qualified else None
    return {"total": total, "qualified": qualified, "unqualified": max(0, total - qualified),
            "pct": pct, "cost_per_qualified": cpq}


def _camp_cols(vtype):
    if vtype == "ecommerce":
        return ["Inversión", "ROAS", "Ventas", "CPA"]
    return ["Inversión", "Leads", "CPL", "CTR"]


def _camp_rows(account, start, end, vtype, h):
    from sqlalchemy import func
    rows = (CampaignMetric.query
            .join(Campaign, Campaign.id == CampaignMetric.campaign_id)
            .filter(Campaign.account_id == account.id,
                    CampaignMetric.date >= start, CampaignMetric.date <= end)
            .with_entities(
                Campaign.name, Campaign.status,
                func.sum(CampaignMetric.cost), func.sum(CampaignMetric.conversions),
                func.sum(CampaignMetric.conversion_value), func.sum(CampaignMetric.impressions),
                func.sum(CampaignMetric.clicks))
            .group_by(Campaign.id).order_by(func.sum(CampaignMetric.cost).desc()).all())
    out = []
    for name, status, cost, conv, val, imp, clk in rows:
        cost, conv, val, imp, clk = [float(x or 0) for x in (cost, conv, val, imp, clk)]
        ctr = (clk / imp * 100) if imp else None
        if vtype == "ecommerce":
            out.append({"name": name, "status": status, "c1": _money(cost),
                        "c2": _ratio(val / cost if cost else None), "c3": f"{conv:,.0f}",
                        "c4": _money(cost / conv if conv else None), "c4_bad": False})
        else:
            out.append({"name": name, "status": status, "c1": _money(cost),
                        "c2": f"{conv:,.0f}", "c3": _money(cost / conv if conv else None),
                        "c4": _pct(ctr), "c4_bad": False})
    return out


def _daily(account, start, end, vtype, h):
    rows = metrics.account_daily(account.id, start, end)
    labels = [r["date"] for r in rows]
    result_label = {"ecommerce": "Ventas", "mensajes": "Mensajes", "leads": "Leads"}[vtype]
    cost_label = {"ecommerce": "CPA", "mensajes": "Costo/mensaje", "leads": "CPL"}[vtype]
    inv = [r["cost"] for r in rows]
    res = [r["conversions"] for r in rows]
    cpr = [(r["cost"] / r["conversions"]) if r["conversions"] else None for r in rows]
    return {
        "has_data": bool(rows),
        "labels": labels,
        "series": [
            {"label": "Inversión", "data": inv, "color": "#3333FF", "format": "money"},
            {"label": result_label, "data": res, "color": "#22E0BE", "format": "int"},
            {"label": cost_label, "data": cpr, "color": "#FFE100", "format": "money"},
        ],
    }
