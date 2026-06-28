"""F7 — admin (reclasificar/editar) + reporte (MoM/YoY)."""
from datetime import date

from webapp.constants import (
    PANEL_LEADS,
    PLATFORM_FACEBOOK_ADS,
    STATUS_ACTIVO,
    STATUS_PENDIENTE,
    VALUE_MANUAL_CLOSE,
)
from webapp.models import Account, Client, MonthlyHistory
from webapp.services import admin as admin_svc
from webapp.services import report_builder


def test_classify_pending_account(session):
    c = Client(slug="c", name="C", margin_pct=0.35)
    session.add(c)
    session.flush()
    a = Account(platform=PLATFORM_FACEBOOK_ADS, external_account_id="a", name="Nueva",
                status=STATUS_PENDIENTE, panel_type=None, is_active=True)
    session.add(a)
    session.commit()
    admin_svc.classify_account(a, client_id=c.id, panel_type=PANEL_LEADS,
                               capture_methods=["messages"], primary_capture="messages",
                               value_source=VALUE_MANUAL_CLOSE, purpose="ventas_leads")
    assert a.panel_type == PANEL_LEADS
    assert a.status == STATUS_ACTIVO          # sale de pendiente
    assert a.value_source == VALUE_MANUAL_CLOSE


def test_set_margin_and_targets(session):
    c = Client(slug="c", name="C")
    session.add(c)
    session.flush()
    a = Account(platform=PLATFORM_FACEBOOK_ADS, external_account_id="a", name="A",
                client_id=c.id, panel_type=PANEL_LEADS, is_active=True)
    session.add(a)
    session.commit()
    admin_svc.set_margin(c, 0.50)
    admin_svc.set_targets(a, target_cpa=120, monthly_budget=8000, monthly_fee=5000)
    assert c.margin_pct == 0.50
    assert c.margin_pct_source == "manual"
    assert a.target_cpa == 120.0
    assert a.monthly_fee == 5000.0


def test_report_build_with_mom_yoy(session):
    c = Client(slug="rum", name="Ruma", margin_pct=0.35, monthly_fee=11000)
    session.add(c)
    session.flush()
    a = Account(platform=PLATFORM_FACEBOOK_ADS, external_account_id="a", name="Ruma",
                client_id=c.id, panel_type=PANEL_LEADS, monthly_fee=11000, is_active=True, currency="MXN")
    session.add(a)
    session.flush()
    # mes actual + mes pasado + año pasado
    for (y, m, monto) in [(2026, 6, 50000), (2026, 5, 40000), (2025, 6, 30000)]:
        session.add(MonthlyHistory(account_id=a.id, client_id=c.id, platform=a.platform,
                                   year=y, month=m, inversion=5000, ventas=20, monto_venta=monto,
                                   currency="MXN"))
    session.commit()
    rep = report_builder.build(c, PLATFORM_FACEBOOK_ADS, 2026, 6)
    assert rep["cur"]["sum_monto"] == 50000
    assert rep["mom"]["sum_monto"] == 40000      # mes pasado
    assert rep["yoy_data"]["sum_monto"] == 30000  # año pasado
    assert "rentable" in rep["headline"]
