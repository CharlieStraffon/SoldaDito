"""F7 branded: herramientas hub + cotización + páginas de marca."""
import re

from webapp.models import Client
from webapp.services import quoting


def test_herramientas_hub(client):
    r = client.get("/herramientas")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Generar reporte" in body
    assert "Revisión de creativos" in body
    assert "Carga manual de conversiones" in body
    assert "Cotización" in body


def test_quote_calc_canonical():
    # objetivo 50, cpa 200 -> presupuesto 10000; ingreso 50*1500=75000;
    # costo 10000+11000=21000; roi=(75000*0.30)/21000=1.07x -> rentable
    q = quoting.calc(objetivo=50, cpa=200, margin=0.30, ticket=1500, honorarios=11000)
    assert q["presupuesto"] == 10000
    assert q["ingreso"] == 75000
    assert round(q["roi"], 2) == 1.07
    assert q["rentable"] is True


def test_quote_not_profitable():
    q = quoting.calc(objetivo=10, cpa=500, margin=0.30, ticket=800, honorarios=5000)
    # presupuesto 5000; ingreso 8000; costo 10000; roi=(8000*.3)/10000=0.24x
    assert q["roi"] < 1
    assert q["rentable"] is False


def test_cotizacion_post(client, session):
    c = Client(slug="rum", name="Ruma", margin_pct=0.30, monthly_fee=11000)
    session.add(c)
    session.commit()
    tok = re.search(r'name="_csrf" value="([^"]+)"',
                    client.get("/herramientas/cotizacion").get_data(as_text=True)).group(1)
    r = client.post("/herramientas/cotizacion",
                    data={"_csrf": tok, "client_id": c.id, "objetivo": "50", "cpa": "200",
                          "margin": "0.30", "ticket": "1500", "honorarios": "11000"})
    assert r.status_code == 200
    assert "Presupuesto sugerido" in r.get_data(as_text=True)


def test_creativos_empty_state(client):
    r = client.get("/herramientas/creativos")
    assert r.status_code == 200
    assert "revisión de creativos" in r.get_data(as_text=True)
