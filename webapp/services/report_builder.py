"""Generador de reportes (F7). El motor financiero se mantiene (D10); aquí el ensamblado
y una narrativa opcional con Sonnet. Comparativa MoM y YoY.
"""
from config import Config
from ..models import MonthlyHistory
from . import engagement as eng


def _prev_month(year, month):
    return (year - 1, 12) if month == 1 else (year, month - 1)


def build(client, platform, year, month):
    cur = eng.compute_month(client, platform, year, month)
    pm_y, pm_m = _prev_month(year, month)
    mom = eng.compute_month(client, platform, pm_y, pm_m)
    yoy = eng.compute_month(client, platform, year - 1, month)

    accounts = eng.engagement_accounts(client.id, platform)
    rows = []
    for a in accounts:
        mh = MonthlyHistory.query.filter_by(account_id=a.id, year=year, month=month).first()
        rows.append({"account": a, "mh": mh})

    headline = _headline(cur, mom, yoy)
    return {
        "client": client, "platform": platform, "year": year, "month": month,
        "cur": cur, "mom": mom, "yoy_data": yoy, "rows": rows, "headline": headline,
    }


def _delta(a, b):
    if a is None or b in (None, 0):
        return None
    return (a - b) / b * 100.0


def _headline(cur, mom, yoy):
    if not cur:
        return "Sin datos para el periodo."
    roi = cur.get("roi")
    util = cur.get("utilidad_neta")
    status = "rentable" if (util is not None and util > 0) else "no rentable aún"
    mom_roi = _delta(roi, mom.get("roi") if mom else None)
    extra = f" ROI {mom_roi:+.0f}% vs mes pasado." if mom_roi is not None else ""
    return f"Engagement {status}.{extra}"


def narrative(report):
    """Narrativa con Sonnet (perezosa, guardada por el caller). Fallback sin red."""
    cur = report["cur"]
    if not Config.ANTHROPIC_API_KEY or not cur:
        return report["headline"]
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        prompt = (
            "Eres analista de marketing. Redacta un resumen ejecutivo breve (3-4 frases), en español, "
            "para el cliente, sobre el desempeño del mes. No inventes números; usa solo estos:\n"
            f"Cliente: {report['client'].name}. Plataforma: {report['platform']}. "
            f"ROI: {cur.get('roi')}. Utilidad neta: {cur.get('utilidad_neta')}. CAC: {cur.get('cac')}. "
            f"Inversión: {cur.get('sum_inversion')}. Ventas: {cur.get('sum_ventas')}. "
            f"Monto: {cur.get('sum_monto')}. Honorarios: {cur.get('honorarios')}."
        )
        resp = client.messages.create(model=Config.MODEL_ANALYST, max_tokens=400,
                                      messages=[{"role": "user", "content": prompt}])
        return "".join(getattr(b, "text", "") for b in resp.content).strip() or report["headline"]
    except Exception:  # noqa
        return report["headline"]
