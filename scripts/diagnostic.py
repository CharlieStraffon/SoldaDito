"""Diagnóstico de fin de fase. Corre esquema + seed idempotente + chequeos.

Uso: python -m scripts.diagnostic
Imprime un reporte y devuelve exit code != 0 si algo falla crítico.
"""
import sys
from collections import Counter

from webapp import create_app
from webapp.constants import (
    PANEL_ECOMMERCE,
    PANEL_LEADS,
    PLATFORM_FACEBOOK_ADS,
    PLATFORM_GOOGLE_ADS,
    STATUS_PENDIENTE,
    VALUE_AUTO_PLATFORM,
)
from webapp.database import db
from webapp.models import Account, Client, MonthlyHistory, TeamMember


def _hr(title):
    print("\n" + "=" * 64)
    print(title)
    print("=" * 64)


def run():
    app = create_app()
    failures = []
    with app.app_context():
        _hr("1. ESQUEMA")
        db.create_all()
        tables = sorted(db.metadata.tables.keys())
        print(f"  tablas: {len(tables)} -> {', '.join(tables)}")

        _hr("2. SEED IDEMPOTENTE (corre 2x)")
        from scripts.seed import seed_all
        r1 = seed_all(verbose=False)
        n_acc1 = Account.query.count()
        n_cli1 = Client.query.count()
        r2 = seed_all(verbose=False)
        n_acc2 = Account.query.count()
        n_cli2 = Client.query.count()
        print(f"  roster: {r1['roster_source']} ({r1['roster_count']} filas)")
        print(f"  cuentas: corrida1={n_acc1}  corrida2={n_acc2}")
        print(f"  clientes: corrida1={n_cli1}  corrida2={n_cli2}")
        if n_acc1 != n_acc2 or n_cli1 != n_cli2:
            failures.append("Seed NO idempotente (cambian conteos)")
        else:
            print("  OK idempotente")

        _hr("3. CATEGORIZACIÓN")
        accts = Account.query.all()
        by_platform = Counter(a.platform for a in accts)
        by_panel = Counter(a.panel_type or "(pendiente)" for a in accts)
        by_currency = Counter(a.currency for a in accts)
        by_status = Counter(a.status for a in accts)
        pendientes = [a for a in accts if a.panel_type is None]
        print(f"  total cuentas: {len(accts)}")
        print(f"  por plataforma: {dict(by_platform)}")
        print(f"  por panel: {dict(by_panel)}")
        print(f"  por moneda: {dict(by_currency)}")
        print(f"  por estado: {dict(by_status)}")
        print(f"  pendiente_de_clasificar: {len(pendientes)}")

        # Toda cuenta clasificada resuelve panel ∈ {ecommerce, leads}
        bad_panel = [a.name for a in accts if a.panel_type not in (None, PANEL_ECOMMERCE, PANEL_LEADS)]
        if bad_panel:
            failures.append(f"panel_type inválido en: {bad_panel}")

        _hr("4. CHEQUEOS DE LA MATRIZ")
        checks = [
            ("ruma", PANEL_ECOMMERCE, None),
            ("cch", PANEL_ECOMMERCE, None),
            ("skyhigh", PANEL_ECOMMERCE, None),
            ("ser_rizada", PANEL_LEADS, VALUE_AUTO_PLATFORM),  # excepción
            ("poliestirenos", PANEL_LEADS, None),
            ("multi_encomiendas", PANEL_LEADS, None),
        ]
        for slug, exp_panel, exp_value in checks:
            cli = Client.query.filter_by(slug=slug).first()
            if not cli:
                print(f"  · {slug}: (sin cliente en roster)")
                continue
            cli_accts = [a for a in accts if a.client_id == cli.id]
            panels = set(a.panel_type for a in cli_accts if a.panel_type)
            note = ""
            if cli_accts:
                if exp_panel not in panels and panels:
                    failures.append(f"{slug}: panel {panels} != esperado {exp_panel}")
                if exp_value:
                    has_auto = any(a.value_source == exp_value for a in cli_accts)
                    note = f" value_source={exp_value}:{'OK' if has_auto else 'FALTA'}"
                    if not has_auto:
                        failures.append(f"{slug}: falta value_source {exp_value}")
            print(f"  · {slug}: {len(cli_accts)} cuentas, panel={panels or '—'}{note}")

        _hr("5. HISTÓRICO / TEAM")
        print(f"  team_members: {TeamMember.query.count()}  (esperado >= 2)")
        print(f"  monthly_history: {MonthlyHistory.query.count()} filas")
        if TeamMember.query.count() < 2:
            failures.append("faltan TeamMembers (Irving/Carlos)")

        _hr("6. BOOT / HEALTHZ")
        c = app.test_client()
        resp = c.get("/healthz")
        print(f"  /healthz -> {resp.status_code} {resp.get_json()}")
        if resp.status_code != 200:
            failures.append("healthz no responde 200")

    _hr("RESULTADO")
    if failures:
        print("  ✗ FALLAS:")
        for f in failures:
            print(f"     - {f}")
        return 1
    print("  ✓ Todo OK")
    return 0


if __name__ == "__main__":
    sys.exit(run())
