"""F5 — baseline 'tu normal' + motor de alertas + persistencia + ruteo."""
from datetime import date, timedelta

from webapp.constants import (
    PANEL_LEADS,
    PLATFORM_GOOGLE_ADS,
    SEVERITY_CRITICAL,
    SEVERITY_PERFORMANCE,
    VALUE_MANUAL_CLOSE,
)
from webapp.models import Account, Alert, Campaign, CampaignMetric, Client, TeamMember
from webapp.services import alerts as A
from webapp.services import baseline


def _acct(session, platform=PLATFORM_GOOGLE_ADS):
    carlos = TeamMember(slug="carlos", name="Carlos", role="Google")
    session.add(carlos)
    c = Client(slug="cli", name="Cli", margin_pct=0.35)
    session.add(c)
    session.flush()
    a = Account(platform=platform, external_account_id="act", name="Cli Google",
                client_id=c.id, panel_type=PANEL_LEADS, value_source=VALUE_MANUAL_CLOSE,
                is_active=True, currency="MXN", assigned_to_id=carlos.id)
    session.add(a)
    session.flush()
    camp = Campaign(account_id=a.id, platform=platform, external_campaign_id="c", name="C")
    session.add(camp)
    session.flush()
    return a, camp, carlos


def _add(session, camp, platform, d, cost, conv):
    session.add(CampaignMetric(campaign_id=camp.id, date=d, platform=platform,
                               cost=cost, conversions=conv, clicks=int(cost), conversion_value=0.0))


def test_baseline_median(session):
    a, camp, _ = _acct(session)
    anchor = date(2026, 6, 30)
    # 40 días normales: cost 100, conv 10 -> cost_per_result 10
    for i in range(3, 43):
        _add(session, camp, a.platform, anchor - timedelta(days=i), 100.0, 10)
    session.commit()
    n = baseline.recompute_account(a, as_of=anchor)
    assert n > 0
    bl = baseline.get(a.id, "cost_per_result", 90)
    assert bl is not None
    assert abs(bl.normal_value - 10.0) < 0.5


def test_sustained_cpl_spike_is_critical(session):
    a, camp, carlos = _acct(session)
    anchor = date(2026, 6, 30)
    for i in range(3, 43):
        _add(session, camp, a.platform, anchor - timedelta(days=i), 100.0, 10)  # normal CPL=10
    # últimos 3 días: CPL ~20 (cost 200, conv 10) -> +100% sostenido (>23%)
    for i in (0, 1, 2):
        _add(session, camp, a.platform, anchor - timedelta(days=i), 200.0, 10)
    session.commit()
    baseline.recompute_account(a, as_of=anchor)
    detected = A.detect_for_account(a, anchor)
    spike = next((d for d in detected if d["kind"] == "cpl_spike"), None)
    assert spike is not None
    assert spike["severity"] == SEVERITY_CRITICAL
    assert spike["days_sustained"] == 3
    # persistencia + ruteo
    A.persist(a, anchor, detected)
    row = Alert.query.filter_by(account_id=a.id, kind="cpl_spike").first()
    assert row.pushed is True                 # crítica se empuja
    assert row.routed_to_id == carlos.id      # ruteada a Carlos (Google)


def test_single_day_breach_not_critical(session):
    a, camp, _ = _acct(session)
    anchor = date(2026, 6, 30)
    for i in range(3, 43):
        _add(session, camp, a.platform, anchor - timedelta(days=i), 100.0, 10)
    # solo HOY rompe; ayer/antier normales -> no sostenido
    _add(session, camp, a.platform, anchor, 200.0, 10)
    _add(session, camp, a.platform, anchor - timedelta(days=1), 100.0, 10)
    _add(session, camp, a.platform, anchor - timedelta(days=2), 100.0, 10)
    session.commit()
    baseline.recompute_account(a, as_of=anchor)
    detected = A.detect_for_account(a, anchor)
    spike = next((d for d in detected if d["kind"] == "cpl_spike"), None)
    assert spike is not None
    assert spike["severity"] == SEVERITY_PERFORMANCE   # vigilar, no crítico


def test_account_silent_is_critical(session):
    a, camp, _ = _acct(session)
    anchor = date(2026, 6, 30)
    for i in range(1, 8):
        _add(session, camp, a.platform, anchor - timedelta(days=i), 100.0, 10)
    # hoy sin gasto -> silenciada
    session.commit()
    baseline.recompute_account(a, as_of=anchor)
    detected = A.detect_for_account(a, anchor)
    assert any(d["kind"] == "account_silent" and d["severity"] == SEVERITY_CRITICAL for d in detected)
