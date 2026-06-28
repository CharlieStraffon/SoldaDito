"""ActionLog (append-only): el cruce acción <-> resultado, antes perdido (dolor #1 Irving).

Captura al menos budget_change con histórico (old/new) + hipótesis. Otros tipos se suman.
"""
from datetime import datetime

from ..constants import ACTION_BUDGET_CHANGE, ACTION_TYPES
from ..database import db
from ..models import ActionLog


def log_action(account, action_type, old_value=None, new_value=None, note=None, by_id=None, at=None):
    if action_type not in ACTION_TYPES:
        action_type = "hypothesis"
    entry = ActionLog(
        account_id=account.id,
        action_type=action_type,
        old_value=str(old_value) if old_value is not None else None,
        new_value=str(new_value) if new_value is not None else None,
        note=note,
        by_id=by_id,
        at=at or datetime.utcnow(),
    )
    db.session.add(entry)
    db.session.commit()
    return entry


def change_budget(account, new_budget, note=None, by_id=None):
    """Cambia el presupuesto de la cuenta y registra el histórico (old -> new)."""
    old = account.monthly_budget
    account.monthly_budget = float(new_budget) if new_budget not in (None, "") else None
    entry = log_action(account, ACTION_BUDGET_CHANGE, old_value=old,
                       new_value=account.monthly_budget, note=note, by_id=by_id)
    db.session.commit()
    return entry


def recent(account_id, limit=20):
    return (ActionLog.query.filter_by(account_id=account_id)
            .order_by(ActionLog.at.desc()).limit(limit).all())


def all_actions(action_type=None, limit=200):
    q = ActionLog.query
    if action_type:
        q = q.filter_by(action_type=action_type)
    return q.order_by(ActionLog.at.desc()).limit(limit).all()
