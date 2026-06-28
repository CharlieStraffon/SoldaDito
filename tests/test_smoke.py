"""F0 smoke: la app levanta, el esquema existe, healthz responde, modelos crean filas."""
from webapp.database import db
from webapp.models import Account, Client, TeamMember
from webapp.constants import PLATFORM_FACEBOOK_ADS


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


def test_schema_has_core_tables(app):
    tables = set(db.metadata.tables.keys())
    for t in [
        "team_members", "notification_preferences", "clients", "accounts",
        "measurement_profiles", "campaigns", "campaign_metrics", "monthly_history",
        "monthly_targets", "account_baselines", "alerts", "action_log",
    ]:
        assert t in tables, f"falta tabla {t}"


def test_can_create_rows(session):
    tm = TeamMember(slug="irving", name="Irving", role="Meta")
    session.add(tm)
    c = Client(slug="ruma", name="RUMA", margin_pct=0.30)
    session.add(c)
    session.flush()
    a = Account(platform=PLATFORM_FACEBOOK_ADS, external_account_id="act_1",
                name="RUMA Meta", client_id=c.id, panel_type="ecommerce")
    session.add(a)
    session.commit()
    assert Account.query.count() == 1
    assert Client.query.first().effective_margin() == 0.30
