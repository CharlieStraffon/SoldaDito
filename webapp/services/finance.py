"""Motor financiero canónico (ADR-002 §5). Una sola definición de ROI (D1).

DOS NIVELES:
  cuenta-mes (operativo, sin fee):
    cpl   = inversión / prospectos              (leads)
    cpa   = inversión / ventas
    roas  = monto_venta / inversión
    aov   = monto_venta / ventas
    %conv = ventas / (prospectos | clics)
    cpv   = inversión / vacantes                (purpose=vacantes)
    utilidad_antes_honorarios = monto × margin − inversión

  engagement-mes (cliente × plataforma; suma cuentas de la misma moneda):
    cac           = (ΣAds + honorarios) / Σventas
    utilidad_neta = Σmonto × margin − honorarios − ΣAds
    roi           = (Σmonto × margin) / (ΣAds + honorarios)     ← CANÓNICO (D1)
    %anuncios     = Σventas / ventas_totales        (solo si ventas_totales)

Reglas:
  · margin de Client (default 0.35); honorarios del engagement.
  · value_source=manual_close sin captura -> "pendiente_de_captura" (no cero).
  · purpose=vacantes -> sin ROI/ROAS; muestra CPV.
  · plataformas NUNCA se suman; el rollup solo agrega cuentas de la misma plataforma.
"""
from .. constants import (
    DEFAULT_MARGIN_PCT,
    PURPOSE_VACANTES,
    VALUE_MANUAL_CLOSE,
)


def safe_div(num, den):
    """División protegida: None si el denominador es 0/None o el numerador es None."""
    if num is None or not den:
        return None
    return num / den


def resolve_margin(margin_pct):
    """Margen efectivo: el del cliente o el default 0.35. Nunca hardcodear en cálculo."""
    return DEFAULT_MARGIN_PCT if margin_pct is None else margin_pct


def pct(num, den):
    """Porcentaje (ratio × 100) protegido."""
    r = safe_div(num, den)
    return None if r is None else r * 100.0


# --------------------------------------------------------------------------- #
# Nivel cuenta-mes
# --------------------------------------------------------------------------- #
def compute_account_month(
    inversion,
    prospectos=None,
    clics=None,
    ventas=None,
    monto=None,
    margin_pct=None,
    purpose=None,
    value_source=None,
    base_conv="prospectos",
):
    """Métricas operativas de una cuenta-mes (sin fee). Devuelve dict con None donde no aplica."""
    margin = resolve_margin(margin_pct)
    inversion = inversion or 0.0

    out = {
        "inversion": inversion,
        "cpl": None, "cpa": None, "roas": None, "aov": None,
        "conv_pct": None, "cpv": None, "roi": None,
        "utilidad_antes_honorarios": None,
        "status": "completo",
    }

    # --- Vacantes: solo CPV, sin valor/ROI ---
    if purpose == PURPOSE_VACANTES:
        out["cpv"] = safe_div(inversion, prospectos)
        out["status"] = "vacantes"
        return out

    # --- Resultado primario (costo/resultado SIEMPRE se puede calcular) ---
    out["cpl"] = safe_div(inversion, prospectos)

    # --- Valor: para manual_close sin captura -> pendiente (no cero) ---
    value_pending = value_source == VALUE_MANUAL_CLOSE and (ventas is None and monto is None)
    if value_pending:
        out["status"] = "pendiente_de_captura"
        return out

    out["cpa"] = safe_div(inversion, ventas)
    out["roas"] = safe_div(monto, inversion)
    out["aov"] = safe_div(monto, ventas)
    base = prospectos if base_conv == "prospectos" else clics
    out["conv_pct"] = pct(ventas, base)
    if monto is not None:
        out["utilidad_antes_honorarios"] = monto * margin - inversion
    return out


# --------------------------------------------------------------------------- #
# Nivel engagement-mes (cliente × plataforma)
# --------------------------------------------------------------------------- #
def compute_engagement(
    sum_inversion,
    sum_ventas,
    sum_monto,
    margin_pct=None,
    honorarios=0.0,
    ventas_totales=None,
):
    """Rentabilidad real de un engagement. ROI canónico (D1)."""
    margin = resolve_margin(margin_pct)
    sum_inversion = sum_inversion or 0.0
    honorarios = honorarios or 0.0
    sum_monto = sum_monto or 0.0
    denom = sum_inversion + honorarios
    margin_value = sum_monto * margin

    roi = safe_div(margin_value, denom)
    utilidad_neta = margin_value - honorarios - sum_inversion
    cac = safe_div(denom, sum_ventas)
    pct_anuncios = pct(sum_ventas, ventas_totales) if ventas_totales else None

    return {
        "sum_inversion": sum_inversion,
        "sum_ventas": sum_ventas,
        "sum_monto": sum_monto,
        "margin_pct": margin,
        "honorarios": honorarios,
        "cac": cac,
        "utilidad_neta": utilidad_neta,
        "roi": roi,
        "pct_anuncios": pct_anuncios,
        "is_profitable": utilidad_neta > 0,
    }


def compute_engagement_from_rows(rows, margin_pct=None, honorarios=0.0, ventas_totales=None):
    """Suma filas (MonthlyHistory-like dicts/objetos) de la MISMA plataforma/moneda."""
    def g(r, k):
        return r.get(k) if isinstance(r, dict) else getattr(r, k, None)

    sum_inv = sum((g(r, "inversion") or 0.0) for r in rows)
    sum_ventas = sum((g(r, "ventas") or 0.0) for r in rows)
    sum_monto = sum((g(r, "monto_venta") or 0.0) for r in rows)
    return compute_engagement(
        sum_inversion=sum_inv, sum_ventas=sum_ventas, sum_monto=sum_monto,
        margin_pct=margin_pct, honorarios=honorarios, ventas_totales=ventas_totales,
    )
