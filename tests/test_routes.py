"""F3 — el centro de control y el detalle renderizan con datos."""
from datetime import date, timedelta

from webapp.constants import PANEL_LEADS, PLATFORM_FACEBOOK_ADS, VALUE_MANUAL_CLOSE
from webapp.models import Account, Campaign, CampaignMetric, Client


def _seed_one(session):
    c = Client(slug="acme", name="Acme", margin_pct=0.35)
    session.add(c)
    session.flush()
    a = Account(platform=PLATFORM_FACEBOOK_ADS, external_account_id="act_acme",
                name="Acme Meta", client_id=c.id, panel_type=PANEL_LEADS,
                primary_capture_method="messages", value_source=VALUE_MANUAL_CLOSE,
                is_active=True, currency="MXN")
    session.add(a)
    session.flush()
    camp = Campaign(account_id=a.id, platform=PLATFORM_FACEBOOK_ADS,
                    external_campaign_id="c1", name="Camp 1", status="ACTIVE")
    session.add(camp)
    session.flush()
    today = date.today()
    for i in range(40):
        d = today - timedelta(days=i)
        session.add(CampaignMetric(campaign_id=camp.id, date=d, platform=PLATFORM_FACEBOOK_ADS,
                                   cost=100.0, conversions=10, clicks=50, impressions=1000,
                                   conversion_value=0.0, messages=10))
    session.commit()
    return a


def test_root_redirects_to_branded_centro(client):
    r = client.get("/")
    assert r.status_code == 302
    assert "/google" in r.headers["Location"]


def test_centro_renders_with_data(client, session):
    _seed_one(session)
    r = client.get("/facebook")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Acme" in body
    assert "centro de control" in body          # branded shell
    assert "todas las cuentas" in body          # worst-first table
    assert "dito-control.css" in body           # brand system loaded


def test_account_detail_renders(client, session):
    a = _seed_one(session)
    r = client.get(f"/accounts/{a.id}")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Acme Meta" in body               # nombre de la cuenta
    assert "detalle de cuenta" in body        # shell branded
    assert "dito-control.css" in body         # sistema de marca
    assert "análisis IA" in body              # bloque IA


def test_detail_404(client):
    assert client.get("/accounts/99999").status_code == 404
