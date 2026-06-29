"""Centro de control (briefing) — ensambla el contexto de la página de marca.

Reúne, por plataforma (nunca se suman): saludo, resumen, 3 tarjetas temporales
(ayer/semana/mes), feed de anomalías (atención), tabla peor-primero, y el árbol
de clientes del sidebar. Reusa metrics/alerts/categorization/periods.
"""
from datetime import datetime, timedelta

from ..constants import (
    PANEL_ECOMMERCE,
    PLATFORM_FACEBOOK_ADS,
    PLATFORM_GOOGLE_ADS,
    SEVERITY_CRITICAL,
    SEVERITY_POSITIVE,
    ALERT_RESOLVED,
)
from ..models import Account, Alert, Client
from . import categorization as cat
from . import metrics
from . import periods

SLUG_PLATFORM = {"google": PLATFORM_GOOGLE_ADS, "facebook": PLATFORM_FACEBOOK_ADS}
PLATFORM_SLUG = {v: k for k, v in SLUG_PLATFORM.items()}


# --------------------------------------------------------------------------- #
# Helpers de formato
# --------------------------------------------------------------------------- #
def _money(v):
    if v is None:
        return "—"
    return f"${v:,.0f}"


def _ratio(v):
    return f"{v:.1f}x" if v is not None else "—"


def greeting(now=None):
    now = now or datetime.now()
    h = now.hour
    if h < 12:
        return "buenos días"
    if h < 19:
        return "buenas tardes"
    return "buenas noches"


def freshness_human(anchor, now=None):
    now = (now or datetime.now()).date()
    days = (now - anchor).days
    if days <= 0:
        return "hoy"
    if days == 1:
        return "hace 1 día"
    return f"hace {days} días"


# --------------------------------------------------------------------------- #
# Salud de cuenta (dot)
# --------------------------------------------------------------------------- #
def _alerts_by_account():
    out = {}
    for a in Alert.query.filter(Alert.status != ALERT_RESOLVED).all():
        out.setdefault(a.account_id, []).append(a)
    return out


def _dot(account, row, alerts):
    if row and row.get("silent"):
        return "crit"
    sev = {al.severity for al in (alerts or [])}
    if SEVERITY_CRITICAL in sev:
        return "crit"
    if row and row["cur"]["inversion"] == 0:
        return "idle"
    if row and row.get("adverse") and row.get("delta_pct") is not None and abs(row["delta_pct"]) >= 20:
        return "warn"
    if any(s not in (SEVERITY_POSITIVE,) for s in sev):
        return "warn"
    return "ok"


_DOT_STATUS = {"crit": "crítico", "warn": "atención", "ok": "en orden", "idle": "sin gasto"}


# --------------------------------------------------------------------------- #
# Tarjetas temporales (ayer / semana / mes)
# --------------------------------------------------------------------------- #
def _attention_count(platform, preset):
    s, e, _ = periods.resolve(preset)
    p_s, p_e = metrics.prior_period(s, e)
    cur = metrics.aggregate_by_account(s, e)
    prev = metrics.aggregate_by_account(p_s, p_e)
    crit = warn = ok = 0
    for a in Account.query.filter_by(platform=platform, is_active=True).all():
        if cat.is_pending(a):
            continue
        row = metrics.account_row(a, cur.get(a.id), prev.get(a.id))
        if row["silent"]:
            crit += 1
        elif row.get("adverse") and row["delta_pct"] is not None and abs(row["delta_pct"]) >= 20:
            warn += 1
        else:
            ok += 1
    return {"crit": crit, "warn": warn, "ok": ok, "needs": crit + warn}


def _temporal_cards(platform):
    specs = [("ayer", "¿qué pasó ayer?"),
             ("semana_pasada", "¿qué pasó la semana pasada?"),
             ("este_mes", "¿cómo va este mes?")]
    cards = []
    for key, title in specs:
        c = _attention_count(platform, key)
        overall = "crit" if c["crit"] else ("warn" if c["warn"] else "ok")
        signal = (f"{c['needs']} cuenta{'s' if c['needs'] != 1 else ''} necesita"
                  f"{'n' if c['needs'] != 1 else ''} atención" if c["needs"] else "todo en orden")
        cards.append({"title": title, "period": key, "dots": [overall] * 3, "signal": signal})
    return cards


# --------------------------------------------------------------------------- #
# Fila de cuenta (worst-first)
# --------------------------------------------------------------------------- #
def _cells(account, row):
    cur, prev = row["cur"], row["prev"]
    target = account.target_cpa
    cost = cur["costo_resultado"]
    cost_chip = None
    cost_ctx = ""
    if target:
        cost_ctx = f"obj {_money(target)}"
        if cost is not None:
            pct = (cost - target) / target * 100
            cost_chip = {"cls": "up-bad" if pct > 0 else "down-good", "text": f"{pct:+.0f}%"}
    roas = cur["roas"]
    roas_cls = ""
    if roas is not None:
        roas_cls = "good" if roas >= (account.target_roas or 3) else ("bad" if roas < 1 else "")
    delta_chip = None
    if row["delta_pct"] is not None:
        delta_chip = {"cls": "up-bad" if row["adverse"] else "down-good",
                      "text": f"{row['delta_pct']:+.0f}%"}
    # Pacing vs presupuesto mensual.
    pace = {"pct": "—", "cls": "", "arrow": "—"}
    if account.monthly_budget:
        mtd = _month_to_date(account)
        elapsed = _month_fraction()
        expected = account.monthly_budget * elapsed
        if expected > 0:
            idx = mtd / expected * 100
            pace = {"pct": f"{idx:.0f}%",
                    "cls": "over" if idx > 110 else ("under" if idx < 90 else "ok"),
                    "arrow": "↑" if idx > 110 else ("↓" if idx < 90 else "●")}
    return {
        "spend": _money(cur["inversion"]),
        "mtd": _money(_month_to_date(account)),
        "currency": account.currency,
        "cost": _money(cost),
        "cost_ctx": cost_ctx,
        "cost_chip": cost_chip,
        "roas": _ratio(roas) if roas is not None else "—",
        "roas_cls": roas_cls,
        "delta_chip": delta_chip,
        "pace": pace,
    }


def _month_to_date(account):
    a = periods.anchor_date()
    s = a.replace(day=1)
    agg = metrics.aggregate_account(account.id, s, a) or {}
    return agg.get("cost", 0)


def _month_fraction():
    a = periods.anchor_date()
    import calendar
    days_in = calendar.monthrange(a.year, a.month)[1]
    return a.day / days_in


# --------------------------------------------------------------------------- #
# Sidebar (clientes)
# --------------------------------------------------------------------------- #
def _sidebar_groups(dots):
    groups = []
    for c in Client.query.order_by(Client.name).all():
        accts = [a for a in c.accounts if a.is_active]
        if not accts:
            continue
        acct_items = []
        worst = "ok"
        for a in accts:
            d = dots.get(a.id, "idle")
            if d == "crit":
                worst = "crit"
            elif d == "warn" and worst != "crit":
                worst = "warn"
            acct_items.append({
                "id": a.id, "label": a.name, "dot": d,
                "plat": "G" if a.platform == PLATFORM_GOOGLE_ADS else "F",
                "slug": PLATFORM_SLUG[a.platform],
            })
        groups.append({"name": c.name, "dot": worst, "accts": acct_items})
    return groups


# --------------------------------------------------------------------------- #
# Anomalías (feed de atención)
# --------------------------------------------------------------------------- #
_SEV_MAP = {SEVERITY_CRITICAL: "critical", SEVERITY_POSITIVE: "positive"}


def _anomalies(platform, limit=6):
    rows = (Alert.query
            .filter(Alert.platform == platform, Alert.status != ALERT_RESOLVED)
            .order_by(Alert.severity.desc(), Alert.date.desc()).all())
    # Críticas primero.
    rows.sort(key=lambda a: 0 if a.severity == SEVERITY_CRITICAL else 1)
    out = []
    for a in rows[:limit]:
        out.append({
            "severity": _SEV_MAP.get(a.severity, "warning"),
            "account_name": a.account.name if a.account else "—",
            "account_id": a.account_id,
            "title": a.kind.replace("_", " "),
            "message": a.ai_explanation or a.message or "Desviación vs tu normal.",
            "kind": a.kind,
        })
    return out


# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #
def build(slug, period):
    platform = SLUG_PLATFORM.get(slug, PLATFORM_GOOGLE_ADS)
    slug = PLATFORM_SLUG[platform]
    s, e, _ = periods.resolve(period)
    p_s, p_e = metrics.prior_period(s, e)
    cur = metrics.aggregate_by_account(s, e)
    prev = metrics.aggregate_by_account(p_s, p_e)
    alerts = _alerts_by_account()

    rows, dots_all = [], {}
    # Dots para TODAS las cuentas activas (sidebar incluye ambas plataformas).
    for a in Account.query.filter_by(is_active=True).all():
        if cat.is_pending(a):
            dots_all[a.id] = "idle"
            continue
        r = metrics.account_row(a, cur.get(a.id), prev.get(a.id))
        dots_all[a.id] = _dot(a, r, alerts.get(a.id))

    accounts_pf = [a for a in Account.query.filter_by(platform=platform, is_active=True).all()
                   if not cat.is_pending(a)]
    for a in accounts_pf:
        r = metrics.account_row(a, cur.get(a.id), prev.get(a.id))
        dot = dots_all.get(a.id, "ok")
        top_alert = next(iter(alerts.get(a.id, [])), None)
        rows.append({
            "id": a.id, "name": a.name,
            "type_label": f"{cat.panel_of(a)} · {'G' if platform == PLATFORM_GOOGLE_ADS else 'F'}",
            "dot": dot, "status_label": _DOT_STATUS[dot],
            "cells": _cells(a, r), "concern": r["concern"],
            "ai": (top_alert.ai_explanation or top_alert.message) if top_alert
                  else "Sin anomalías detectadas para este período.",
        })
    rows.sort(key=lambda x: x["concern"], reverse=True)

    needs = sum(1 for x in rows if x["dot"] in ("crit", "warn"))
    ok = sum(1 for x in rows if x["dot"] == "ok")
    anomalies = _anomalies(platform)
    anomaly_counts = {"critical": sum(1 for x in anomalies if x["severity"] == "critical")}
    anchor = periods.anchor_date()

    b = {
        "slug": slug, "platform": platform,
        "platform_label": "Google Ads" if platform == PLATFORM_GOOGLE_ADS else "Facebook Ads",
        "period": period or "30d",
        "period_label": periods.label_for(period or "30d", s, e),
        "start_date": s.isoformat(), "end_date": e.isoformat(),
        "freshness": {"human": freshness_human(anchor)},
        "summary": {"needs_attention": needs, "ok": ok, "total": len(rows)},
        "cards": _temporal_cards(platform),
        "anomalies": anomalies, "anomaly_counts": anomaly_counts,
        "accounts": rows,
    }
    return {
        "b": b,
        "greeting": greeting(),
        "presets": periods.PRESET_ITEMS,
        "sidebar_groups": _sidebar_groups(dots_all),
    }
