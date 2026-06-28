"""F1 — Rollup engagement: el fee se cuenta UNA vez (no doble-conteo multi-ubicación)."""
from webapp.constants import PANEL_LEADS, PLATFORM_FACEBOOK_ADS
from webapp.database import db
from webapp.models import Account, Client, MonthlyHistory
from webapp.services import engagement


def _make_multilocation(session):
    c = Client(slug="multi", name="Multi-Encomiendas", margin_pct=0.35)
    session.add(c)
    session.flush()
    # 4 cuentas en Meta, mismo fee 26500 (de STATUS) — NO debe sumarse 4x.
    accts = []
    for i, loc in enumerate(["Houston", "Dallas", "Austin", "Louisiana"]):
        a = Account(platform=PLATFORM_FACEBOOK_ADS, external_account_id=f"act_{i}",
                    name=f"Multi {loc}", client_id=c.id, panel_type=PANEL_LEADS,
                    location_label=loc, monthly_fee=26500, currency="USD", is_active=True)
        session.add(a)
        accts.append(a)
    session.flush()
    for a in accts:
        session.add(MonthlyHistory(account_id=a.id, client_id=c.id,
                                   platform=PLATFORM_FACEBOOK_ADS, year=2026, month=1,
                                   inversion=1000.0, ventas=5, monto_venta=10000.0))
    session.commit()
    return c


def test_fee_counted_once(session):
    c = _make_multilocation(session)
    eng = engagement.compute_month(c, PLATFORM_FACEBOOK_ADS, 2026, 1)
    assert eng["honorarios"] == 26500          # UNA vez, no 4×26500=106000
    assert eng["sum_inversion"] == 4000.0      # 4 × 1000
    assert eng["sum_ventas"] == 20             # 4 × 5
    assert eng["sum_monto"] == 40000.0         # 4 × 10000
    # roi = (40000*0.35)/(4000+26500) = 14000/30500 = 0.459
    assert round(eng["roi"], 3) == 0.459
    assert eng["n_accounts"] == 4


def test_resolve_honorarios_single_value(session):
    c = Client(slug="x", name="X")
    session.add(c)
    session.flush()
    a1 = Account(platform=PLATFORM_FACEBOOK_ADS, external_account_id="a1", client_id=c.id, monthly_fee=5000)
    a2 = Account(platform=PLATFORM_FACEBOOK_ADS, external_account_id="a2", client_id=c.id, monthly_fee=5000)
    session.add_all([a1, a2])
    session.commit()
    assert engagement.resolve_honorarios([a1, a2]) == 5000   # no 10000
