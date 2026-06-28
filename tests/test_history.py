"""F4 — desglose mensual + cierre congela snapshots."""
from datetime import date

from webapp.constants import (
    PANEL_ECOMMERCE,
    PANEL_LEADS,
    PLATFORM_FACEBOOK_ADS,
    VALUE_MANUAL_CLOSE,
)
from webapp.models import Account, Campaign, CampaignMetric, Client, MonthlyHistory
from webapp.services import history as hist


def _ecom(session, margin=0.35):
    c = Client(slug="rum", name="Ruma", margin_pct=margin, monthly_fee=11000)
    session.add(c)
    session.flush()
    a = Account(platform=PLATFORM_FACEBOOK_ADS, external_account_id="act_r", name="Ruma Meta",
                client_id=c.id, panel_type=PANEL_ECOMMERCE, monthly_fee=11000,
                currency="MXN", is_active=True)
    session.add(a)
    session.flush()
    camp = Campaign(account_id=a.id, platform=PLATFORM_FACEBOOK_ADS, external_campaign_id="c", name="C")
    session.add(camp)
    session.flush()
    for day in (1, 2, 3):
        session.add(CampaignMetric(campaign_id=camp.id, date=date(2026, 1, day),
                                   platform=PLATFORM_FACEBOOK_ADS, cost=1000.0,
                                   purchases=10, purchases_value=20000.0, conversions=10,
                                   conversion_value=20000.0, clicks=200))
    session.commit()
    return c, a


def test_build_refreshes_api_and_computes(session):
    c, a = _ecom(session)
    row = hist.get_or_build(a, 2026, 1)
    assert row.inversion == 3000.0          # 3×1000 API
    assert row.ventas == 30                 # 3×10 purchases
    assert row.monto_venta == 60000.0
    assert round(row.roas, 2) == 20.0       # 60000/3000
    # cpa = 3000/30 = 100
    assert round(row.cpa, 2) == 100.0


def test_close_freezes_snapshots(session):
    c, a = _ecom(session, margin=0.35)
    hist.get_or_build(a, 2026, 1)
    n = hist.close_engagement(c, PLATFORM_FACEBOOK_ADS, 2026, 1)
    assert n == 1
    row = MonthlyHistory.query.filter_by(account_id=a.id, year=2026, month=1).first()
    assert row.is_closed is True
    assert row.margin_pct_snapshot == 0.35
    assert row.fee_snapshot == 11000

    # Cambiar el margen del cliente DESPUÉS no altera el mes cerrado.
    c.margin_pct = 0.60
    session.commit()
    hist.get_or_build(a, 2026, 1)            # re-evaluar
    row = MonthlyHistory.query.filter_by(account_id=a.id, year=2026, month=1).first()
    assert row.margin_pct_snapshot == 0.35   # congelado


def test_closed_month_blocks_manual_edit(session):
    c = Client(slug="x", name="X", margin_pct=0.35)
    session.add(c)
    session.flush()
    a = Account(platform=PLATFORM_FACEBOOK_ADS, external_account_id="x", name="X Meta",
                client_id=c.id, panel_type=PANEL_LEADS, value_source=VALUE_MANUAL_CLOSE,
                currency="MXN", is_active=True)
    session.add(a)
    session.commit()
    hist.get_or_build(a, 2026, 1)
    hist.close_engagement(c, PLATFORM_FACEBOOK_ADS, 2026, 1)
    row, err = hist.save_manual(a, 2026, 1, {"ventas": "5", "monto_venta": "1000"})
    assert err is not None                    # bloqueado
    assert row.ventas != 5
