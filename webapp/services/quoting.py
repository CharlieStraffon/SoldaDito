"""Cotización — calcula presupuesto/honorario y si el CPA esperado es rentable.

ROI canónico (D1): (ingreso × margen) / (presupuesto + honorarios).
El CPA esperado puede venir capturado o derivarse del baseline ("tu normal") de una cuenta.
"""
from . import baseline


def calc(objetivo, cpa, margin, ticket, honorarios=0.0):
    """Devuelve el desglose de la cotización. Inputs ya resueltos (floats)."""
    objetivo = objetivo or 0
    cpa = cpa or 0
    honorarios = honorarios or 0
    margin = margin if margin is not None else 0.35
    ticket = ticket or 0
    presupuesto = objetivo * cpa
    ingreso = objetivo * ticket
    costo_total = presupuesto + honorarios
    margen_valor = ingreso * margin
    roi = (margen_valor / costo_total) if costo_total else None
    utilidad = margen_valor - costo_total
    return {
        "objetivo": objetivo, "cpa": cpa, "margin": margin, "ticket": ticket,
        "honorarios": honorarios, "presupuesto": presupuesto, "ingreso": ingreso,
        "costo_total": costo_total, "roi": roi, "utilidad": utilidad,
        "rentable": (roi is not None and roi >= 1),
    }


def cpa_from_baseline(account_id):
    bl = baseline.get(account_id, "cost_per_result", 90)
    return bl.normal_value if bl else None
