"""Desglose mensual editable (cuenta-mes) — contexto + guardado de celda (AJAX).

Columnas por tipo visual. Celdas editables (API/manual) en gris; calculadas read-only.
ROI CANÓNICO (D1): (monto × margin) / (inversión + honorarios) — ratio, no porcentaje.
Honorarios por fila viven en fee_snapshot (editable mientras abierto; se congela al cerrar).
"""
from ..constants import PLATFORM_FACEBOOK_ADS, PLATFORM_GOOGLE_ADS
from ..database import db
from ..models import Account, AccountBaseline, MonthlyHistory
from . import categorization as cat
from . import history

VALID_TYPES = ["ecommerce", "leads", "mensajes"]


def _money(v):
    return f"${v:,.0f}" if v is not None else "—"


def _ratio(v):
    return f"{v:.1f}x" if v else "—"


def _margin(account):
    return account.client.effective_margin() if account.client else 0.35


def compute_calc(account, row):
    """Calculados canónicos para una fila. Devuelve dict de floats (o None)."""
    vt = cat.visual_type(account)
    inv = row.inversion or 0
    fee = row.fee_snapshot or 0
    total = inv + fee
    margin = (row.margin_pct_snapshot if row.is_closed and row.margin_pct_snapshot is not None
              else _margin(account))
    monto = row.monto_venta
    out = {}
    if vt == "ecommerce":
        out["aov"] = (monto / row.ventas) if (monto and row.ventas) else None
        out["cpa"] = (inv / row.ventas) if row.ventas else None
        out["roas"] = (monto / inv) if inv else None
        out["roi"] = (monto * margin / total) if (monto and total) else None
    elif vt == "leads":
        out["cpl"] = (inv / row.prospectos) if row.prospectos else None
        out["roi"] = (monto * margin / total) if (monto and total) else None
    else:  # mensajes
        out["cpm"] = (inv / row.prospectos) if row.prospectos else None
        out["roi"] = None
    return out


def _fmt_calc(vt, calc):
    """Formatea calc para mostrar/AJAX."""
    f = {}
    if vt == "ecommerce":
        f["aov"] = _money(calc.get("aov"))
        f["cpa"] = _money(calc.get("cpa"))
        f["roas"] = _ratio(calc.get("roas"))
        f["roi"] = _ratio(calc.get("roi")) if calc.get("roi") is not None else "n/a"
    elif vt == "leads":
        f["cpl"] = _money(calc.get("cpl"))
        f["roi"] = _ratio(calc.get("roi")) if calc.get("roi") is not None else "n/a"
    else:
        f["cpm"] = _money(calc.get("cpm"))
        f["roi"] = "n/a"
    return f


# Columnas (label, key, kind, src) por tipo. kind: mes|edit|calc_money|calc_x|calc_roi|st
def _cols(vt):
    if vt == "ecommerce":
        return [
            ("Mes", "mes", "mes", None),
            ("Inversión", "inversion", "edit", "api"),
            ("Ventas", "ventas", "edit", "api"),
            ("Monto", "monto_venta", "edit", "api"),
            ("AOV", "aov", "calc_money", None),
            ("CPA", "cpa", "calc_money", None),
            ("ROAS", "roas", "calc_x", None),
            ("Honorarios", "fee", "edit", "man"),
            ("ROI", "roi", "calc_roi", None),
            ("Estado", "st", "st", None),
        ]
    if vt == "leads":
        return [
            ("Mes", "mes", "mes", None),
            ("Inversión", "inversion", "edit", "api"),
            ("Leads", "prospectos", "edit", "api"),
            ("Convertidos", "ventas", "edit", "man"),
            ("Valor generado", "monto_venta", "edit", "man"),
            ("CPL", "cpl", "calc_money", None),
            ("Honorarios", "fee", "edit", "man"),
            ("ROI", "roi", "calc_roi", None),
            ("Estado", "st", "st", None),
        ]
    return [
        ("Mes", "mes", "mes", None),
        ("Inversión", "inversion", "edit", "api"),
        ("Mensajes", "prospectos", "edit", "api"),
        ("Costo/mensaje", "cpm", "calc_money", None),
        ("Honorarios", "fee", "edit", "man"),
        ("ROI", "roi", "calc_roi", None),
        ("Estado", "st", "st", None),
    ]


_MONTHS = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
_FIELD_RAW = {"inversion": "inversion", "ventas": "ventas", "monto_venta": "monto_venta",
              "prospectos": "prospectos", "fee": "fee_snapshot"}


def _row_view(account, row, vt):
    calc = compute_calc(account, row)
    fmt = _fmt_calc(vt, calc)
    cells = []
    for label, key, kind, src in _cols(vt):
        if kind == "mes":
            cells.append({"kind": "mes", "text": f"{_MONTHS[row.month]} {row.year}"})
        elif kind == "st":
            cells.append({"kind": "st"})
        elif kind == "edit":
            raw = getattr(row, _FIELD_RAW[key], None)
            cells.append({"kind": "edit", "edit": True, "field": key,
                          "raw": ("" if raw is None else raw), "src": src, "label": label})
        elif kind == "calc_roi":
            cells.append({"kind": "calc_pct", "key": key, "fmt": fmt.get(key, "—")})
        elif kind == "calc_x":
            cells.append({"kind": "calc_x", "key": key, "fmt": fmt.get(key, "—")})
        else:
            cells.append({"kind": "calc", "key": key, "fmt": fmt.get(key, "—")})
    return {"year": row.year, "month": row.month, "is_closed": row.is_closed, "cells": cells}


def context(account):
    vt = cat.visual_type(account)
    rows = (MonthlyHistory.query.filter_by(account_id=account.id)
            .order_by(MonthlyHistory.year, MonthlyHistory.month).all())
    # Asegura que cada fila tenga sus calculados al día.
    row_views = [_row_view(account, r, vt) for r in rows]

    # Resumen (promedios sobre meses cerrados).
    closed = [r for r in rows if r.is_closed]
    fee = next((a.monthly_fee for a in [account] if a.monthly_fee is not None), 0) or 0
    summary = _summary(account, vt, closed, fee)
    fee_note = (f"Honorarios de {_money(fee)}/mes (editable inline) incluidos en el costo total y el ROI."
                if vt != "mensajes"
                else f"Honorarios de {_money(fee)}/mes. En cuentas de mensajes no se calcula ROI — solo volumen y costo por mensaje.")
    return {
        "account": account, "client_type": vt,
        "cols": [{"label": l, "key": k, "kind": kk, "src": s} for l, k, kk, s in _cols(vt)],
        "rows": row_views, "summary": summary, "fee_note": fee_note,
        "ref": _ref(account, vt),
        "margin": _margin(account),
        "back_slug": "google" if account.platform == PLATFORM_GOOGLE_ADS else "facebook",
    }


def _summary(account, vt, closed, fee):
    import statistics
    def avg(vals):
        vals = [v for v in vals if v is not None]
        return statistics.mean(vals) if vals else None
    rois = [compute_calc(account, r).get("roi") for r in closed]
    if vt == "ecommerce":
        return [
            {"l": "ROI prom. (con honorarios)", "v": (_ratio(avg(rois)) if avg(rois) else "n/a"), "s": f"{len(closed)} mes(es) cerrados", "good": True},
            {"l": "Valor generado", "v": _money(sum((r.monto_venta or 0) for r in closed)), "s": f"{len(closed)} mes(es)"},
            {"l": "CPA prom.", "v": _money(avg([compute_calc(account, r).get('cpa') for r in closed])), "s": "tu normal"},
            {"l": "Inversión prom.", "v": _money(avg([r.inversion for r in closed])), "s": "meses cerrados"},
        ]
    if vt == "leads":
        return [
            {"l": "ROI prom. (con honorarios)", "v": (_ratio(avg(rois)) if avg(rois) else "n/a"), "s": f"{len(closed)} mes(es) cerrados", "good": True},
            {"l": "Valor generado", "v": _money(sum((r.monto_venta or 0) for r in closed)), "s": f"{len(closed)} mes(es)"},
            {"l": "Costo por lead prom.", "v": _money(avg([compute_calc(account, r).get('cpl') for r in closed])), "s": "tu normal"},
            {"l": "Inversión prom.", "v": _money(avg([r.inversion for r in closed])), "s": "meses cerrados"},
        ]
    return [
        {"l": "Costo/mensaje prom.", "v": _money(avg([compute_calc(account, r).get('cpm') for r in closed])), "s": "tu normal"},
        {"l": "Mensajes/mes prom.", "v": (f"{avg([r.prospectos for r in closed]):,.0f}" if avg([r.prospectos for r in closed]) else "—"), "s": "meses cerrados"},
        {"l": "Inversión prom.", "v": _money(avg([r.inversion for r in closed])), "s": "meses cerrados"},
        {"l": "ROI", "v": "n/a", "s": "no se monetiza"},
    ]


def _ref(account, vt):
    """Fila 'tu normal' (baseline) alineada a las columnas."""
    bl = {b.metric: b.normal_value for b in AccountBaseline.query.filter_by(account_id=account.id, window_days=90).all()}
    if not bl:
        return None
    ref = {"mes": "tu normal"}
    for _, key, kind, _src in _cols(vt):
        if key == "cpl" or key == "cpa":
            ref[key] = _money(bl.get("cost_per_result"))
        elif key == "roas":
            ref[key] = _ratio(bl.get("roas"))
        elif key == "inversion":
            ref[key] = _money(bl.get("spend"))
        elif kind not in ("mes", "st"):
            ref[key] = "—"
    return ref


# --------------------------------------------------------------------------- #
def update_cell(account, year, month, field, value):
    """Guarda una celda (AJAX). Crea la fila si falta. Devuelve calc recomputado."""
    if field not in _FIELD_RAW:
        return {"ok": False, "error": "campo inválido"}
    row = MonthlyHistory.query.filter_by(account_id=account.id, year=year, month=month).first()
    if row is None:
        row = MonthlyHistory(account_id=account.id, year=year, month=month,
                             platform=account.platform, client_id=account.client_id,
                             currency=account.currency,
                             panel_type_snapshot=cat.panel_of(account))
        db.session.add(row)
    if row.is_closed:
        return {"ok": False, "error": "El mes está cerrado"}
    v = None if value in (None, "") else float(value)
    setattr(row, _FIELD_RAW[field], v)
    if field in ("ventas", "monto_venta") and v is not None:
        setattr(row, "ventas_source" if field == "ventas" else "monto_source", "manual")
    history.recompute(account, row)
    db.session.commit()
    vt = cat.visual_type(account)
    calc = compute_calc(account, row)
    fmt = _fmt_calc(vt, calc)
    roi = calc.get("roi")
    return {"ok": True, "calc": fmt, "roi_pos": bool(roi and roi >= 1), "roi_neg": bool(roi and roi < 1)}


def platform_counts():
    out = {}
    for p in (PLATFORM_GOOGLE_ADS, PLATFORM_FACEBOOK_ADS):
        out[p] = sum(1 for a in Account.query.filter_by(platform=p, is_active=True).all()
                     if not cat.is_pending(a))
    return out


def close_month(account, year, month):
    """Cierra una cuenta-mes: congela margen/fee, alimenta baseline."""
    row = MonthlyHistory.query.filter_by(account_id=account.id, year=year, month=month).first()
    if not row or row.is_closed:
        return False
    from datetime import datetime
    row.margin_pct_snapshot = _margin(account)
    if row.fee_snapshot is None:
        row.fee_snapshot = account.monthly_fee or 0
    row.is_closed = True
    row.closed_at = datetime.utcnow()
    db.session.commit()
    try:
        from . import baseline
        baseline.recompute_account(account)
    except Exception:  # noqa
        pass
    return True


def close_history(account):
    """Cierra todos los meses con datos (excepto el mes en curso)."""
    from . import periods
    a = periods.anchor_date()
    n = 0
    for row in MonthlyHistory.query.filter_by(account_id=account.id).all():
        if row.is_closed:
            continue
        if (row.year, row.month) == (a.year, a.month):
            continue  # mes en curso queda abierto
        if close_month(account, row.year, row.month):
            n += 1
    return n


def set_objetivo(account, value):
    account.client_type_override = value if value in VALID_TYPES else None
    db.session.commit()


def classified_accounts(platform):
    return [a for a in Account.query.filter_by(platform=platform, is_active=True).order_by(Account.name).all()
            if not cat.is_pending(a)]
