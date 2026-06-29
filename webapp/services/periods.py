"""Resolución de periodos para el date picker (presets + rango + comparar).

Presets alineados al mockup: Hoy · Ayer · Esta semana · Últimos 7 · Semana pasada ·
Últimos 14 · Últimos 15 · Este mes · Últimos 30 · Mes pasado · Todo el tiempo + custom.
"""
from datetime import date, timedelta

from . import metrics

# (key, label) en orden de aparición en el dropdown.
PRESET_ITEMS = [
    ("hoy", "Hoy"),
    ("ayer", "Ayer"),
    ("esta_semana", "Esta semana"),
    ("7d", "Últimos 7 días"),
    ("semana_pasada", "Semana pasada"),
    ("14d", "Últimos 14 días"),
    ("15d", "Últimos 15 días"),
    ("este_mes", "Este mes"),
    ("30d", "Últimos 30 días"),
    ("mes_pasado", "Mes pasado"),
    ("todo", "Todo el tiempo"),
]
PRESETS = [k for k, _ in PRESET_ITEMS]
PRESET_LABELS = dict(PRESET_ITEMS)
PRESET_LABELS["custom"] = "Personalizado"

_MONTHS_ES = ["", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def anchor_date():
    """Fecha ancla: el último día con datos (los datos pueden venir con rezago)."""
    return metrics.latest_metric_date() or date.today()


def _first_metric_date():
    from sqlalchemy import func
    from ..database import db
    from ..models import CampaignMetric
    return db.session.query(func.min(CampaignMetric.date)).scalar()


def resolve(preset=None, start=None, end=None):
    """Devuelve (start, end, label). Default: últimos 30 días desde el ancla."""
    a = anchor_date()
    if start and end:
        return start, end, "custom"
    if preset and preset.startswith("custom:"):
        parts = preset[7:].split(",")
        if len(parts) == 2:
            s, e = parse_date(parts[0]), parse_date(parts[1])
            if s and e:
                return s, e, "custom"
    p = preset or "30d"
    if p == "hoy":
        return a, a, p
    if p == "ayer":
        d = a - timedelta(days=1)
        return d, d, p
    if p == "esta_semana":
        return a - timedelta(days=a.weekday()), a, p
    if p == "7d":
        return a - timedelta(days=6), a, p
    if p == "semana_pasada":
        this_mon = a - timedelta(days=a.weekday())
        last_sun = this_mon - timedelta(days=1)
        return last_sun - timedelta(days=6), last_sun, p
    if p == "14d":
        return a - timedelta(days=13), a, p
    if p == "15d":
        return a - timedelta(days=14), a, p
    if p == "este_mes":
        return a.replace(day=1), a, p
    if p == "mes_pasado":
        first_this = a.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        return last_prev.replace(day=1), last_prev, p
    if p == "todo":
        return (_first_metric_date() or a - timedelta(days=365)), a, p
    return a - timedelta(days=29), a, "30d"


def label_for(preset, start, end):
    """Etiqueta corta para el pill (preset conocido o rango legible)."""
    if preset and preset in PRESET_LABELS and preset != "custom":
        return PRESET_LABELS[preset]
    return f"{start.day} {_MONTHS_ES[start.month]} – {end.day} {_MONTHS_ES[end.month]}"


def parse_date(s):
    try:
        return date.fromisoformat(s) if s else None
    except (ValueError, TypeError):
        return None
