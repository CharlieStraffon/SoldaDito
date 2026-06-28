"""CSRF mínimo por sesión. Regla dura: CSRF en toda ruta POST que mute estado."""
import secrets

from flask import session, request, abort

_CSRF_KEY = "_csrf_token"


def generate_csrf_token() -> str:
    if _CSRF_KEY not in session:
        session[_CSRF_KEY] = secrets.token_urlsafe(32)
    return session[_CSRF_KEY]


def verify_csrf(submitted: str) -> bool:
    expected = session.get(_CSRF_KEY)
    return bool(expected) and secrets.compare_digest(str(submitted or ""), str(expected))


def require_csrf():
    """Llamar al inicio de cada handler POST mutante."""
    token = request.form.get("_csrf") or request.headers.get("X-CSRF-Token")
    if not verify_csrf(token):
        abort(400, description="CSRF token inválido o ausente")
