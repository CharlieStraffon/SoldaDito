"""Categorización EXPLÍCITA por cuenta. Nunca deriva el panel del evento de conversión.

El bug original (Poliestirenos/Celeste/Gymex) venía de derivar el tipo del
conversion_category de la API. Aquí panel_type es un dato sembrado/editado; el
conversion_category solo se usó como SUGERENCIA en el seed, jamás en runtime.
"""
from ..constants import (
    CAPTURE_COST_LABEL,
    CAPTURE_MESSAGES,
    CAPTURE_RESULT_LABEL,
    PANEL_ECOMMERCE,
    PANEL_LEADS,
    PURPOSE_VACANTES,
    VALUE_AUTO_PLATFORM,
    VALUE_MANUAL_CLOSE,
)


def panel_of(account):
    """Panel EXPLÍCITO. Prioridad: override del cliente > panel_type de la cuenta.
    Devuelve None si está pendiente_de_clasificar. NUNCA mira conversion_category."""
    client = getattr(account, "client", None)
    if client and client.client_type_override:
        return client.client_type_override
    return account.panel_type


def is_pending(account):
    return panel_of(account) is None


def visual_type(account):
    """Tipo visual del panel: ecommerce / mensajes / leads. Honra el override del desglose."""
    ov = getattr(account, "client_type_override", None)
    if ov in ("ecommerce", "leads", "mensajes"):
        return ov
    if panel_of(account) == PANEL_ECOMMERCE:
        return "ecommerce"
    if primary_capture(account) == CAPTURE_MESSAGES:
        return "mensajes"
    return "leads"


def is_vacantes(account):
    return account.purpose == PURPOSE_VACANTES


def primary_capture(account):
    if account.primary_capture_method:
        return account.primary_capture_method
    caps = account.capture_methods or []
    return caps[0] if caps else None


def result_label(account):
    """Etiqueta del 'resultado' héroe del panel (de la captura primaria explícita)."""
    if is_vacantes(account):
        return "aplicación"
    if panel_of(account) == PANEL_ECOMMERCE:
        return "compra"
    cap = primary_capture(account)
    return CAPTURE_RESULT_LABEL.get(cap, "resultado")


def cost_label(account):
    if is_vacantes(account):
        return "CPV"
    if panel_of(account) == PANEL_ECOMMERCE:
        return "CPA"
    cap = primary_capture(account)
    return CAPTURE_COST_LABEL.get(cap, "costo/resultado")


def value_source_badge(account):
    if account.value_source == VALUE_AUTO_PLATFORM:
        return ("auto", "automático (pixel/feed)")
    if account.value_source == VALUE_MANUAL_CLOSE:
        return ("manual", "cierre manual")
    return ("?", "sin definir")


def capture_labels(account):
    """Todas las capturas (para mostrar Gymex/Edimex con ambas)."""
    return [CAPTURE_RESULT_LABEL.get(c, c) for c in (account.capture_methods or [])]


def summary(account):
    """Resumen de categorización para UI/diagnóstico."""
    return {
        "panel": panel_of(account),
        "pending": is_pending(account),
        "result_label": result_label(account),
        "cost_label": cost_label(account),
        "value_source": account.value_source,
        "value_badge": value_source_badge(account),
        "primary_capture": primary_capture(account),
        "captures": account.capture_methods or [],
        "purpose": account.purpose,
        "is_vacantes": is_vacantes(account),
    }
