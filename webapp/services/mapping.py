"""Resuelve un nombre de cuenta (sucio, de la API) a su categorización curada.

Devuelve client_slug + location + purpose; el panel_type/capture/value se toman
del cliente (por plataforma) en el seed. Sin match -> None (pendiente_de_clasificar).
"""
import unicodedata

from scripts.mapping_config import (
    CLIENTS,
    NAME_PATTERNS,
    STATUS_BY_NAME,
)


def normalize(text):
    if not text:
        return ""
    t = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii")
    return t.lower()


def resolve(name):
    """-> {client_slug, location_label, purpose} o None si no hay patrón."""
    n = normalize(name)
    for keywords, slug, location, purpose in NAME_PATTERNS:
        if all(kw in n for kw in keywords):
            return {"client_slug": slug, "location_label": location, "purpose": purpose}
    return None


def status_override_for_name(name):
    """Estado especial por nombre (Escampa/Irona pausado, Micah's inactivo)."""
    n = normalize(name)
    for keywords, status in STATUS_BY_NAME:
        if all(kw in n for kw in keywords):
            return status
    return None


def client_config(slug):
    return CLIENTS.get(slug)


def platform_config(slug, platform):
    cfg = CLIENTS.get(slug) or {}
    return (cfg.get("platforms") or {}).get(platform) or {}
