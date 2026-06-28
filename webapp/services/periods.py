"""Resolución de periodos para el date picker (presets + rango + comparar)."""
import calendar
from datetime import date, timedelta

from . import metrics

PRESETS = ["7d", "30d", "90d", "this_month", "last_month"]
PRESET_LABELS = {
    "7d": "Últimos 7 días", "30d": "Últimos 30 días", "90d": "Últimos 90 días",
    "this_month": "Este mes", "last_month": "Mes pasado", "custom": "Personalizado",
}


def anchor_date():
    """Fecha ancla: el último día con datos (los datos pueden venir con rezago)."""
    return metrics.latest_metric_date() or date.today()


def resolve(preset=None, start=None, end=None):
    """Devuelve (start, end, preset_label). Default: últimos 30 días desde el ancla."""
    a = anchor_date()
    if start and end:
        return start, end, "custom"
    preset = preset or "30d"
    if preset == "7d":
        return a - timedelta(days=6), a, preset
    if preset == "90d":
        return a - timedelta(days=89), a, preset
    if preset == "this_month":
        return a.replace(day=1), a, preset
    if preset == "last_month":
        first_this = a.replace(day=1)
        last_prev_end = first_this - timedelta(days=1)
        return last_prev_end.replace(day=1), last_prev_end, preset
    # default 30d
    return a - timedelta(days=29), a, "30d"


def parse_date(s):
    try:
        return date.fromisoformat(s) if s else None
    except (ValueError, TypeError):
        return None
