"""F6 — ActionLog (presupuesto con histórico) + MeasurementProfile visible."""
from webapp.constants import ACTION_BUDGET_CHANGE, PANEL_LEADS, PLATFORM_FACEBOOK_ADS
from webapp.models import Account, ActionLog, Client, MeasurementProfile
from webapp.services import actions as act


def _acct(session, budget=5000):
    c = Client(slug="c", name="C")
    session.add(c)
    session.flush()
    a = Account(platform=PLATFORM_FACEBOOK_ADS, external_account_id="a", name="A",
                client_id=c.id, panel_type=PANEL_LEADS, monthly_budget=budget, is_active=True)
    session.add(a)
    session.commit()
    return a


def test_budget_change_records_history(session):
    a = _acct(session, budget=5000)
    act.change_budget(a, 7000, note="Escalamos por buen CPL")
    e = ActionLog.query.filter_by(account_id=a.id, action_type=ACTION_BUDGET_CHANGE).first()
    assert e is not None
    assert e.old_value == "5000.0" or e.old_value == "5000"
    assert e.new_value == "7000.0"
    assert a.monthly_budget == 7000.0
    assert "Escalamos" in e.note


def test_action_log_is_append_only_history(session):
    a = _acct(session)
    act.change_budget(a, 6000)
    act.change_budget(a, 4000)
    act.log_action(a, "hypothesis", note="Probar nuevo creativo UGC")
    entries = act.recent(a.id)
    assert len(entries) == 3                       # histórico completo, nada se pierde
    assert entries[0].action_type == "hypothesis"  # más reciente primero


def test_measurement_offline_flag(session):
    a = _acct(session)
    mp = MeasurementProfile(account_id=a.id, offline_import=False)
    session.add(mp)
    session.commit()
    # bandera de riesgo: offline_import = NO en leads
    assert a.measurement.offline_import is False
