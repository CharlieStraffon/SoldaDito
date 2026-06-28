"""Triage de anomalías con Haiku (explicable y SILENCIOSO por defecto).

Genera 1-2 frases en español explicando una alerta. Perezoso y cacheado en
Alert.ai_explanation. Si no hay API key o falla la red, devuelve un fallback estático
(nunca rompe la UI). Sonnet se reserva para reportes (F7).
"""
from config import Config
from ..database import db


def _fallback(alert):
    return alert.message or "Desviación detectada vs tu normal."


def explain(alert, force=False):
    """Devuelve (y cachea) la explicación de una alerta. Usa Haiku si hay API key."""
    if alert.ai_explanation and not force:
        return alert.ai_explanation
    if not Config.ANTHROPIC_API_KEY:
        return _fallback(alert)
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        acct = alert.account
        prompt = (
            "Eres un analista de marketing. Explica en 1-2 frases, en español, claro y accionable, "
            "esta anomalía de una cuenta publicitaria. No inventes números.\n"
            f"Cuenta: {acct.name} ({acct.platform}). Tipo de alerta: {alert.kind}. "
            f"Métrica: {alert.metric}. Observado: {alert.observed_value}. Normal: {alert.normal_value}. "
            f"Delta: {alert.delta_pct}. Días sostenido: {alert.days_sustained}. Severidad: {alert.severity}."
        )
        resp = client.messages.create(
            model=Config.MODEL_TRIAGE, max_tokens=180,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(getattr(b, "text", "") for b in resp.content).strip()
        alert.ai_explanation = text or _fallback(alert)
        db.session.commit()
        return alert.ai_explanation
    except Exception:  # noqa - nunca romper la UI por IA
        return _fallback(alert)
