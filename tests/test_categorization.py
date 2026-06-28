"""F2 — panel_type EXPLÍCITO, nunca derivado del evento (guarda del bug original)."""
from webapp.constants import (
    CAPTURE_MESSAGES,
    PANEL_ECOMMERCE,
    PANEL_LEADS,
    PLATFORM_FACEBOOK_ADS,
    VALUE_AUTO_PLATFORM,
    VALUE_MANUAL_CLOSE,
)
from webapp.models import Account, Client
from webapp.services import categorization as cat


def _acct(session, **kw):
    defaults = dict(platform=PLATFORM_FACEBOOK_ADS, external_account_id="act_x", name="X")
    defaults.update(kw)
    a = Account(**defaults)
    session.add(a)
    session.commit()
    return a


def test_panel_is_explicit_not_derived_from_event(session):
    # conversion_category dice PURCHASE (evento), pero panel_type sembrado = leads.
    # El bug original devolvería ecommerce; el sistema correcto respeta leads.
    a = _acct(session, conversion_category="PURCHASE", panel_type=PANEL_LEADS,
              primary_capture_method=CAPTURE_MESSAGES, value_source=VALUE_MANUAL_CLOSE)
    assert cat.panel_of(a) == PANEL_LEADS          # NO mira conversion_category
    assert cat.result_label(a) == "conversación"
    assert cat.cost_label(a) == "costo/conversación"


def test_unmapped_account_is_pending(session):
    a = _acct(session, panel_type=None)
    assert cat.is_pending(a) is True
    assert cat.panel_of(a) is None


def test_ecommerce_labels(session):
    a = _acct(session, panel_type=PANEL_ECOMMERCE, value_source=VALUE_AUTO_PLATFORM)
    assert cat.result_label(a) == "compra"
    assert cat.cost_label(a) == "CPA"
    assert cat.value_source_badge(a)[0] == "auto"


def test_vacantes_overrides_to_cpv(session):
    a = _acct(session, panel_type=PANEL_LEADS, purpose="vacantes")
    assert cat.is_vacantes(a) is True
    assert cat.cost_label(a) == "CPV"


def test_client_override_wins(session):
    c = Client(slug="c", name="C", client_type_override=PANEL_ECOMMERCE)
    session.add(c)
    session.flush()
    a = _acct(session, panel_type=PANEL_LEADS, client_id=c.id)
    # override del cliente manda sobre el panel de la cuenta
    assert cat.panel_of(a) == PANEL_ECOMMERCE
