"""F1 — Motor financiero. TESTS PRIMERO (contrato ADR-002 §5).

Definición canónica única (D1):
    ROI = (Σmonto × margin_pct) / (ΣAds + honorarios)        -> siempre >= 0
    Utilidad Neta = Σmonto × margin_pct − honorarios − ΣAds   -> con signo

Un "mes de arranque con ROI negativo" = engagement NO rentable: utilidad_neta < 0
y ROI < 1.0 (la margen-valor no cubre Ads+fee). No se reintroduce la fórmula vieja
de "utilidad/costo" (que daba 3.71 para el caso de aceptación) — D1 es la única.
"""
import pytest

from webapp.services import finance as F


# --------------------------------------------------------------------------- #
# Caso de aceptación de la plantilla (enero, panel leads)
# --------------------------------------------------------------------------- #
ACCEPT = dict(
    prospectos=509, inversion=500.09, ventas=35, monto=15800.0,
    margin=0.35, honorarios=675.0, ventas_totales=430,
)


def test_acceptance_cuenta_mes():
    cm = F.compute_account_month(
        inversion=ACCEPT["inversion"], prospectos=ACCEPT["prospectos"],
        ventas=ACCEPT["ventas"], monto=ACCEPT["monto"], margin_pct=ACCEPT["margin"],
        base_conv="prospectos",
    )
    assert round(cm["cpl"], 2) == 0.98
    assert round(cm["aov"], 2) == 451.43
    assert round(cm["conv_pct"], 2) == 6.88
    assert round(cm["cpa"], 2) == 14.29
    assert round(cm["roas"], 2) == 31.59
    # utilidad antes de honorarios = 15800*0.35 - 500.09 = 5029.91
    assert round(cm["utilidad_antes_honorarios"], 2) == 5029.91


def test_acceptance_engagement():
    eng = F.compute_engagement(
        sum_inversion=ACCEPT["inversion"], sum_ventas=ACCEPT["ventas"],
        sum_monto=ACCEPT["monto"], margin_pct=ACCEPT["margin"],
        honorarios=ACCEPT["honorarios"], ventas_totales=ACCEPT["ventas_totales"],
    )
    assert round(eng["cac"], 2) == 33.57
    assert round(eng["utilidad_neta"], 2) == 4354.91
    assert round(eng["roi"], 2) == 4.71          # CANÓNICO
    assert round(eng["pct_anuncios"], 2) == 8.14
    assert eng["roi"] >= 0


# --------------------------------------------------------------------------- #
# Caso de arranque NO rentable ("ROI negativo" -> utilidad_neta < 0, roi < 1)
# --------------------------------------------------------------------------- #
def test_startup_month_loss():
    # inversión alta, ventas pocas: margen-valor no cubre Ads+fee.
    eng = F.compute_engagement(
        sum_inversion=8000.0, sum_ventas=3, sum_monto=6000.0,
        margin_pct=0.35, honorarios=5000.0,
    )
    # ROI canónico = (6000*0.35)/(8000+5000) = 2100/13000 = 0.1615
    assert round(eng["roi"], 4) == 0.1615
    assert eng["roi"] < 1.0                       # por debajo de break-even
    # utilidad_neta = 2100 - 5000 - 8000 = -10900
    assert round(eng["utilidad_neta"], 2) == -10900.00
    assert eng["utilidad_neta"] < 0
    assert eng["is_profitable"] is False


# --------------------------------------------------------------------------- #
# Reglas de integridad
# --------------------------------------------------------------------------- #
def test_margin_default_035_when_missing():
    assert F.resolve_margin(None) == 0.35
    assert F.resolve_margin(0.60) == 0.60


def test_pct_anuncios_only_with_total():
    eng = F.compute_engagement(sum_inversion=100, sum_ventas=10, sum_monto=1000,
                               margin_pct=0.35, honorarios=50, ventas_totales=None)
    assert eng["pct_anuncios"] is None            # se oculta, no n/a ruidoso


def test_vacantes_uses_cpv_no_roi():
    cm = F.compute_account_month(
        inversion=1000.0, prospectos=20, ventas=None, monto=None,
        margin_pct=0.35, purpose="vacantes",
    )
    assert round(cm["cpv"], 2) == 50.0            # 1000/20 vacantes
    assert cm["roas"] is None
    assert cm["roi"] is None


def test_manual_close_pending_capture_not_zero():
    # leads con value_source=manual_close sin captura -> pendiente, no cero.
    cm = F.compute_account_month(
        inversion=500.0, prospectos=100, ventas=None, monto=None,
        margin_pct=0.35, value_source="manual_close", base_conv="prospectos",
    )
    assert cm["cpl"] == 5.0                        # costo/resultado SÍ se calcula
    assert cm["roas"] is None                      # valor pendiente -> sin ROAS
    assert cm["status"] == "pendiente_de_captura"


def test_safe_div_zero():
    assert F.safe_div(10, 0) is None
    assert F.safe_div(10, 2) == 5.0


def test_engagement_sums_accounts_same_currency():
    # 2 ubicaciones de la misma plataforma se suman; honorarios una vez.
    rows = [
        {"inversion": 300.0, "ventas": 10, "monto_venta": 5000.0},
        {"inversion": 200.0, "ventas": 5, "monto_venta": 3000.0},
    ]
    eng = F.compute_engagement_from_rows(rows, margin_pct=0.35, honorarios=675.0)
    assert eng["sum_inversion"] == 500.0
    assert eng["sum_ventas"] == 15
    assert eng["sum_monto"] == 8000.0
    # roi = (8000*0.35)/(500+675) = 2800/1175 = 2.383
    assert round(eng["roi"], 3) == 2.383
