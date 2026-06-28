"""Motor de alertas (ADR-002 §7).

Google (umbrales fijos de Carlos vs 'tu normal', sostenidos 3 días -> crítico):
  CPA ↑≥25% (ecom) · CPL ↑≥23% (leads) · ROAS ↓≥45% · Gasto ↕≥30% · Conversiones ↓≥28%
  + IS perdido >12% (5 días) · 60 clics sin conversión.
Meta (derivado del baseline, conservador): z-score |actual−normal|/dispersión > 2σ.
account_silent (ambas): gastaba y hoy cero -> crítico.

Severidad: crítico / rendimiento / positivo. DÍA 1: solo crítico se EMPUJA (pushed=True).
Persistencia: una desviación no es alerta hasta sostener su ventana (evita el ruido de la
re-escritura de 3 días de Google). Ruteo por assigned_to (Irving=Meta, Carlos=Google).
"""
from datetime import timedelta

from sqlalchemy import func

from ..constants import (
    GOOGLE_CATCHUP_REFRESH_DAYS,
    PANEL_ECOMMERCE,
    PLATFORM_GOOGLE_ADS,
    SEVERITY_CRITICAL,
    SEVERITY_PERFORMANCE,
    SEVERITY_POSITIVE,
    VALUE_AUTO_PLATFORM,
)
from ..database import db
from ..models import Account, Alert, Campaign, CampaignMetric
from . import baseline
from . import categorization as cat

META_Z = 2.0  # z-score conservador (Meta)

# (metric, direction, threshold_pct, persistence_days, kind)
GOOGLE_RULES = [
    ("cost_per_result", "up", None, 3, "cost_spike"),   # threshold por panel (abajo)
    ("roas", "down", 0.45, 3, "roas_drop"),
    ("spend", "both", 0.30, 3, "spend_anomaly"),
    ("conversions", "down", 0.28, 3, "conversions_drop"),
]


def _daily_map(account_id, start, end):
    """{date: {cost, conv, value}} por día."""
    q = (
        db.session.query(
            CampaignMetric.date,
            func.coalesce(func.sum(CampaignMetric.cost), 0),
            func.coalesce(func.sum(CampaignMetric.conversions), 0),
            func.coalesce(func.sum(CampaignMetric.conversion_value), 0),
            func.coalesce(func.sum(CampaignMetric.clicks), 0),
            func.coalesce(func.sum(CampaignMetric.search_budget_lost_impression_share), 0),
        )
        .join(Campaign, Campaign.id == CampaignMetric.campaign_id)
        .filter(Campaign.account_id == account_id)
        .filter(CampaignMetric.date >= start, CampaignMetric.date <= end)
        .group_by(CampaignMetric.date)
    )
    out = {}
    for d, cost, conv, val, clicks, islost in q.all():
        out[d] = {"cost": float(cost), "conv": float(conv), "value": float(val),
                  "clicks": float(clicks), "islost": float(islost)}
    return out


def _metric_value(day, metric, has_real):
    cost, conv, val = day["cost"], day["conv"], day["value"]
    if cost <= 0:
        return None
    if metric == "spend":
        return cost
    if metric == "conversions":
        return conv
    if metric == "cost_per_result":
        return cost / conv if conv > 0 else None
    if metric == "roas":
        return (val / cost) if has_real else None
    return None


def _breached(value, normal, dispersion, direction, threshold_pct, platform):
    """¿La observación rompe el umbral en dirección adversa?"""
    if value is None or normal in (None, 0):
        return False
    if platform == PLATFORM_GOOGLE_ADS:
        delta = (value - normal) / normal
        if direction == "up":
            return delta >= threshold_pct
        if direction == "down":
            return delta <= -threshold_pct
        return abs(delta) >= threshold_pct
    # Meta: z-score
    if not dispersion:
        return False
    z = (value - normal) / dispersion
    if direction == "up":
        return z >= META_Z
    if direction == "down":
        return z <= -META_Z
    return abs(z) >= META_Z


def detect_for_account(account, as_of):
    has_real = cat.panel_of(account) == PANEL_ECOMMERCE or account.value_source == VALUE_AUTO_PLATFORM
    panel = cat.panel_of(account)
    days = _daily_map(account.id, as_of - timedelta(days=10), as_of)
    found = []

    # --- account_silent (crítico): gastaba y hoy cero ---
    today = days.get(as_of)
    prior_window = [days.get(as_of - timedelta(days=i)) for i in range(1, GOOGLE_CATCHUP_REFRESH_DAYS + 5)]
    prior_spend = sum((d["cost"] for d in prior_window if d), 0.0)
    if (today is None or today["cost"] == 0) and prior_spend > 0:
        found.append(dict(kind="account_silent", metric="spend", severity=SEVERITY_CRITICAL,
                          observed_value=0.0, normal_value=None, delta_pct=None, days_sustained=1,
                          message="La cuenta gastaba y hoy no registra inversión."))
        return found  # silenciada domina

    # --- reglas por métrica ---
    for metric, direction, threshold, persistence, kind in GOOGLE_RULES:
        bl = baseline.get(account.id, metric, window=90)
        if bl is None or bl.normal_value is None:
            continue
        thr = threshold
        if metric == "cost_per_result":
            thr = 0.25 if panel == PANEL_ECOMMERCE else 0.23
            kind = "cpa_spike" if panel == PANEL_ECOMMERCE else "cpl_spike"
        # ¿breach sostenido en los últimos `persistence` días?
        breaches = []
        for i in range(persistence):
            d = days.get(as_of - timedelta(days=i))
            if d is None:
                breaches.append(False)
                continue
            v = _metric_value(d, metric, has_real)
            breaches.append(_breached(v, bl.normal_value, bl.dispersion, direction, thr, account.platform))
        if not breaches or breaches[0] is False:
            # también detecta MEJORA (positivo) en métricas clave
            _maybe_positive(found, account, metric, days, as_of, bl, has_real)
            continue
        obs = _metric_value(days.get(as_of), metric, has_real)
        delta = ((obs - bl.normal_value) / bl.normal_value * 100.0) if (obs and bl.normal_value) else None
        sustained = all(breaches)
        severity = SEVERITY_CRITICAL if sustained else SEVERITY_PERFORMANCE
        found.append(dict(kind=kind, metric=metric, severity=severity, observed_value=obs,
                          normal_value=bl.normal_value, delta_pct=delta,
                          days_sustained=sum(1 for b in breaches if b),
                          message=_msg(kind, metric, delta, sustained)))

    # --- IS perdido (solo Google, 5 días) ---
    if account.platform == PLATFORM_GOOGLE_ADS:
        is_breaches = []
        for i in range(5):
            d = days.get(as_of - timedelta(days=i))
            is_breaches.append(bool(d) and d["islost"] > 0.12)
        if is_breaches and all(is_breaches):
            found.append(dict(kind="is_lost_budget", metric="impression_share",
                              severity=SEVERITY_CRITICAL, observed_value=days[as_of]["islost"] * 100,
                              normal_value=12.0, delta_pct=None, days_sustained=5,
                              message="Impression share perdido por presupuesto >12% por 5 días."))

    return found


def _maybe_positive(found, account, metric, days, as_of, bl, has_real):
    """Detecta mejora notable (positivo, silencioso). Solo cost_per_result/roas."""
    if metric not in ("cost_per_result", "roas") or bl.normal_value in (None, 0):
        return
    d = days.get(as_of)
    if not d:
        return
    v = _metric_value(d, metric, has_real)
    if v is None:
        return
    delta = (v - bl.normal_value) / bl.normal_value
    good = (metric == "roas" and delta >= 0.30) or (metric == "cost_per_result" and delta <= -0.25)
    if good:
        found.append(dict(kind=f"{metric}_positive", metric=metric, severity=SEVERITY_POSITIVE,
                          observed_value=v, normal_value=bl.normal_value, delta_pct=delta * 100,
                          days_sustained=1, message="Mejora notable vs tu normal."))


def _msg(kind, metric, delta, sustained):
    d = f"{delta:+.0f}%" if delta is not None else ""
    tail = "sostenido 3 días" if sustained else "hoy (vigilar)"
    labels = {"cpa_spike": "CPA arriba", "cpl_spike": "CPL arriba", "roas_drop": "ROAS abajo",
              "spend_anomaly": "Gasto desviado", "conversions_drop": "Conversiones abajo"}
    return f"{labels.get(kind, metric)} {d} vs tu normal — {tail}."


def persist(account, as_of, detected):
    """Upsert de Alert por (account, date, kind). Rutea y marca pushed (solo crítico día 1)."""
    n = 0
    for a in detected:
        row = Alert.query.filter_by(account_id=account.id, date=as_of, kind=a["kind"]).first()
        if row is None:
            row = Alert(account_id=account.id, date=as_of, kind=a["kind"], status="new")
            db.session.add(row)
        row.platform = account.platform
        row.metric = a.get("metric")
        row.severity = a["severity"]
        row.observed_value = a.get("observed_value")
        row.normal_value = a.get("normal_value")
        row.delta_pct = a.get("delta_pct")
        row.days_sustained = a.get("days_sustained", 1)
        row.message = a.get("message")
        row.routed_to_id = account.assigned_to_id
        row.pushed = a["severity"] == SEVERITY_CRITICAL    # día 1: solo críticas se empujan
        n += 1
    db.session.commit()
    return n


def run_detection(as_of=None):
    """Recalcula baselines y corre detección para todas las cuentas activas."""
    as_of = as_of or db.session.query(func.max(CampaignMetric.date)).scalar()
    if as_of is None:
        return {"accounts": 0, "alerts": 0, "critical": 0}
    baseline.recompute_all(as_of)
    total, crit = 0, 0
    for account in Account.query.filter_by(is_active=True).all():
        if cat.is_pending(account):
            continue
        detected = detect_for_account(account, as_of)
        total += persist(account, as_of, detected)
        crit += sum(1 for d in detected if d["severity"] == SEVERITY_CRITICAL)
    return {"accounts": Account.query.filter_by(is_active=True).count(), "alerts": total,
            "critical": crit, "as_of": as_of.isoformat()}
