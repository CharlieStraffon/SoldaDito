"""Servicios de edición (F7). Los datos ya eran editables por seed/código (D6); aquí la UI.

Marca el origen como 'manual' al editar para no pisarlo en re-seeds (idempotencia §4).
"""
from ..constants import (
    CAPTURE_METHODS,
    PANEL_TYPES,
    PURPOSES,
    STATUS_ACTIVO,
    STATUS_PENDIENTE,
    VALUE_SOURCES,
)
from ..database import db
from ..models import Account, Client, MonthlyTarget


def classify_account(account, *, client_id=None, panel_type=None, capture_methods=None,
                     primary_capture=None, value_source=None, purpose=None, location_label=None):
    if client_id:
        account.client_id = int(client_id)
    if panel_type in PANEL_TYPES:
        account.panel_type = panel_type
    if capture_methods is not None:
        account.capture_methods = [c for c in capture_methods if c in CAPTURE_METHODS]
    if primary_capture in CAPTURE_METHODS:
        account.primary_capture_method = primary_capture
    if value_source in VALUE_SOURCES:
        account.value_source = value_source
    if purpose in PURPOSES:
        account.purpose = purpose
    if location_label is not None:
        account.location_label = location_label or None
    # Si ya tiene panel, sale de pendiente.
    if account.panel_type and account.status == STATUS_PENDIENTE:
        account.status = STATUS_ACTIVO
        account.is_active = True
    db.session.commit()
    return account


def set_margin(client, margin_pct):
    client.margin_pct = float(margin_pct)
    client.margin_pct_source = "manual"
    db.session.commit()
    return client


def set_targets(account, *, target_cpa=None, target_roas=None, monthly_budget=None, monthly_fee=None):
    def _f(v):
        return float(v) if v not in (None, "") else None
    if target_cpa is not None:
        account.target_cpa = _f(target_cpa)
    if target_roas is not None:
        account.target_roas = _f(target_roas)
    if monthly_budget is not None:
        account.monthly_budget = _f(monthly_budget)
    if monthly_fee is not None:
        account.monthly_fee = _f(monthly_fee)
    db.session.commit()
    return account


def set_monthly_target(account, year, month, metric, objetivo):
    t = MonthlyTarget.query.filter_by(account_id=account.id, year=year, month=month, metric=metric).first()
    if t is None:
        t = MonthlyTarget(account_id=account.id, year=year, month=month, metric=metric)
        db.session.add(t)
    t.objetivo = float(objetivo) if objetivo not in (None, "") else None
    db.session.commit()
    return t
