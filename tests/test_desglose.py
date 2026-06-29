"""Desglose branded: render + cell-save (ROI canónico) + objetivo override."""
import re
from datetime import date

from webapp.constants import PANEL_ECOMMERCE, PLATFORM_GOOGLE_ADS
from webapp.models import Account, Client, MonthlyHistory


def _ecom_with_history(session):
    c = Client(slug="rum", name="Ruma", margin_pct=0.30, monthly_fee=11000)
    session.add(c)
    session.flush()
    a = Account(platform=PLATFORM_GOOGLE_ADS, external_account_id="r", name="Ruma Ads",
                client_id=c.id, panel_type=PANEL_ECOMMERCE, monthly_fee=11000,
                currency="MXN", is_active=True)
    session.add(a)
    session.flush()
    session.add(MonthlyHistory(account_id=a.id, client_id=c.id, platform=a.platform,
                               year=2026, month=1, inversion=5000, ventas=30, monto_venta=60000,
                               currency="MXN", panel_type_snapshot=PANEL_ECOMMERCE))
    session.commit()
    return a


def _csrf(body):
    return re.search(r'name="_csrf" value="([^"]+)"', body).group(1)


def test_desglose_renders_branded(client, session):
    a = _ecom_with_history(session)
    r = client.get(f"/desglose/{a.id}")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "desglose mensual" in body
    assert "dtable editable" in body
    assert "data-margin" in body
    assert "Honorarios" in body


def test_cell_save_recomputes_canonical_roi(client, session):
    a = _ecom_with_history(session)
    body = client.get(f"/desglose/{a.id}").get_data(as_text=True)
    tok = _csrf(body)
    # monto 60000, inv 5000, margin 0.30, fee (none yet) -> roi = 60000*0.30/5000 = 3.6x
    r = client.post(f"/desglose/{a.id}/cell",
                    data={"_csrf": tok, "year": "2026", "month": "1", "field": "monto_venta", "value": "60000"})
    j = r.get_json()
    assert j["ok"] is True
    assert j["calc"]["roi"] == "3.6x"          # canónico (ratio), no porcentaje
    assert j["roi_pos"] is True
    # add fee 11000 -> roi = 18000/16000 = 1.1x
    r2 = client.post(f"/desglose/{a.id}/cell",
                     data={"_csrf": tok, "year": "2026", "month": "1", "field": "fee", "value": "11000"})
    assert r2.get_json()["calc"]["roi"] == "1.1x"


def test_cell_save_requires_csrf(client, session):
    a = _ecom_with_history(session)
    r = client.post(f"/desglose/{a.id}/cell",
                    data={"year": "2026", "month": "1", "field": "fee", "value": "1"})
    assert r.status_code == 400


def test_objetivo_override(client, session):
    a = _ecom_with_history(session)
    tok = _csrf(client.get(f"/desglose/{a.id}").get_data(as_text=True))
    client.post(f"/desglose/{a.id}/set-type", data={"_csrf": tok, "client_type": "leads"})
    assert Account.query.get(a.id).client_type_override == "leads"
