"""Seed idempotente de DITO (spec §2).

Orden: TeamMember -> Client -> Account (API o fallback dito.db, enriquecida de la
matriz) -> MeasurementProfile -> MonthlyHistory (histórico cerrado importado).

Idempotencia:
  · upsert por clave estable (slug, (platform, external_account_id), (account,year,month)).
  · El MAPEO (cliente, panel_type, capture, value) se RE-APLICA cada corrida.
  · margin_pct / monthly_fee / targets / budget: se escriben SOLO si están vacíos.
  · Meses cerrados: inmutables. El seed NUNCA borra (ausentes -> inactivo es opcional).
"""
import shutil
import sqlite3
import sys
from pathlib import Path

from config import Config
from webapp import create_app
from webapp.constants import (
    PLATFORM_FACEBOOK_ADS,
    PLATFORM_GOOGLE_ADS,
    STATUS_PENDIENTE,
)
from webapp.database import db
from webapp.models import (
    Account,
    Client,
    MeasurementProfile,
    MonthlyHistory,
    NotificationPreference,
    TeamMember,
)
from webapp.services import mapping
from scripts.mapping_config import CLIENTS, TEAM


# --------------------------------------------------------------------------- #
# 1. Equipo
# --------------------------------------------------------------------------- #
def seed_team():
    members = {}
    for m in TEAM:
        tm = TeamMember.query.filter_by(slug=m["slug"]).first()
        if tm is None:
            tm = TeamMember(slug=m["slug"])
            db.session.add(tm)
        tm.name, tm.email, tm.role = m["name"], m["email"], m["role"]
        db.session.flush()
        pref = m.get("pref") or {}
        np = NotificationPreference.query.filter_by(member_id=tm.id).first()
        if np is None:
            np = NotificationPreference(member_id=tm.id)
            db.session.add(np)
        np.channel = pref.get("channel")
        np.cadence = pref.get("cadence")
        np.anticipation_days = pref.get("anticipation_days")
        np.low_noise = pref.get("low_noise", False)
        members[m["slug"]] = tm
    db.session.commit()
    return members


# --------------------------------------------------------------------------- #
# 2. Clientes
# --------------------------------------------------------------------------- #
def _max_tier(platforms):
    order = ["Diamante", "Importante", "Intermedio", "Bajo"]
    tiers = [p.get("tier") for p in platforms.values() if p.get("tier")]
    for t in order:
        if t in tiers:
            return t
    return None


def seed_clients():
    for slug, cfg in CLIENTS.items():
        c = Client.query.filter_by(slug=slug).first()
        if c is None:
            c = Client(slug=slug)
            db.session.add(c)
        # Estructura: se re-aplica.
        c.name = cfg["name"]
        c.business_type = cfg.get("business_type")
        c.ticket_tier = cfg.get("ticket_tier")
        c.commercial_tier = _max_tier(cfg.get("platforms") or {})
        c.status = cfg.get("status")
        c.fee_currency = cfg.get("currency", "MXN")
        # Margen / fee: solo si vacíos (no pisar ediciones de la app).
        if c.margin_pct is None:
            c.margin_pct = cfg.get("margin_pct")  # None -> el modelo aplica 0.35 por default
            c.margin_pct_source = "config"
        if c.monthly_fee is None:
            fees = [p.get("fee") for p in (cfg.get("platforms") or {}).values() if p.get("fee")]
            c.monthly_fee = max(fees) if fees else None
    db.session.commit()


# --------------------------------------------------------------------------- #
# 3. Roster: API en vivo o fallback al dito.db legacy (solo lectura)
# --------------------------------------------------------------------------- #
def _roster_from_api():
    from webapp.services import sync
    rows = []
    for platform in (PLATFORM_GOOGLE_ADS, PLATFORM_FACEBOOK_ADS):
        try:
            rows.extend(sync.fetch_roster(platform))
        except Exception as e:  # noqa
            print(f"  [seed] roster API {platform} falló: {e}")
    return rows


def _legacy_snapshot():
    """Copia el dito.db legacy a instance/ (lectura), para no tocar el original."""
    src = Config.LEGACY_DB_PATH
    if not src or not Path(src).exists():
        return None
    dst = Path("instance") / "_legacy_snapshot.db"
    shutil.copy(src, dst)
    return str(dst)


def _roster_from_legacy(snap):
    con = sqlite3.connect(f"file:{snap}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT name, platform, external_account_id, currency, account_status "
            "FROM accounts"
        ).fetchall()
    finally:
        con.close()
    return [
        {
            "name": r["name"],
            "platform": r["platform"],
            "external_account_id": r["external_account_id"],
            "currency": r["currency"] or "MXN",
            "account_status": r["account_status"],
        }
        for r in rows
    ]


def get_roster():
    rows = _roster_from_api()
    source = "api"
    if not rows:
        snap = _legacy_snapshot()
        if snap:
            rows = _roster_from_legacy(snap)
            source = "legacy_dito.db"
    return rows, source


# --------------------------------------------------------------------------- #
# 4. Cuentas (enriquecidas de la matriz)
# --------------------------------------------------------------------------- #
def seed_accounts(roster, members):
    stats = {"created": 0, "updated": 0, "pendiente": 0, "classified": 0}
    for row in roster:
        platform = row["platform"]
        ext = row["external_account_id"]
        if not ext:
            continue
        acct = Account.query.filter_by(platform=platform, external_account_id=ext).first()
        if acct is None:
            acct = Account(platform=platform, external_account_id=ext)
            db.session.add(acct)
            stats["created"] += 1
        else:
            stats["updated"] += 1

        # --- API (read-only): re-estampar ---
        acct.name = row.get("name") or acct.name
        acct.currency = row.get("currency") or acct.currency
        acct.account_status = row.get("account_status") or acct.account_status

        # --- Mapeo (se RE-APLICA) ---
        resolved = mapping.resolve(acct.name)
        assignee = members.get("irving") if platform == PLATFORM_FACEBOOK_ADS else members.get("carlos")
        acct.assigned_to_id = assignee.id if assignee else None

        if resolved is None:
            acct.status = mapping.status_override_for_name(acct.name) or STATUS_PENDIENTE
            acct.panel_type = None
            stats["pendiente"] += 1
            db.session.flush()
            _ensure_measurement(acct)
            continue

        slug = resolved["client_slug"]
        client = Client.query.filter_by(slug=slug).first()
        ccfg = CLIENTS.get(slug, {})
        pcfg = mapping.platform_config(slug, platform)

        acct.client_id = client.id if client else None
        acct.panel_type = ccfg.get("panel_type")
        acct.location_label = resolved.get("location_label")
        acct.purpose = resolved.get("purpose") or "ventas_leads"
        acct.capture_methods = pcfg.get("capture") or []
        acct.primary_capture_method = pcfg.get("primary")
        acct.value_source = pcfg.get("value_source")
        acct.commercial_tier = pcfg.get("tier")
        acct.etapa = pcfg.get("etapa")
        # currency override del cliente si la API no la trae confiable
        if ccfg.get("currency") and (not acct.currency or acct.currency == "MXN"):
            acct.currency = ccfg["currency"]

        # Estado: pendiente si no hay panel_type; si no, del cliente.
        override = mapping.status_override_for_name(acct.name)
        if acct.panel_type is None:
            acct.status = override or STATUS_PENDIENTE
            stats["pendiente"] += 1
        else:
            acct.status = override or ccfg.get("status")
            stats["classified"] += 1
        acct.is_active = acct.status not in ("inactivo", "baja")

        # --- fee/budget/targets: SOLO si vacíos (no pisar ediciones) ---
        if acct.monthly_fee is None and pcfg.get("fee") is not None:
            acct.monthly_fee = pcfg["fee"]
        if acct.monthly_budget is None and pcfg.get("budget") is not None:
            acct.monthly_budget = pcfg["budget"]

        db.session.flush()
        _ensure_measurement(acct)
    db.session.commit()
    return stats


def _ensure_measurement(acct):
    mp = MeasurementProfile.query.filter_by(account_id=acct.id).first()
    if mp is None:
        mp = MeasurementProfile(account_id=acct.id)
        db.session.add(mp)
        # leads hoy: offline_import = NO (bandera de riesgo). ecommerce: desconocido.
        from webapp.constants import PANEL_LEADS
        if acct.panel_type == PANEL_LEADS:
            mp.offline_import = False


# --------------------------------------------------------------------------- #
# 6. Histórico de cierres (importa de dito.db legacy)
# --------------------------------------------------------------------------- #
def import_legacy_monthly_history(snap):
    if not snap:
        return 0
    con = sqlite3.connect(f"file:{snap}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    imported = 0
    try:
        # Tablas legacy: monthly_history join accounts (para casar por ext id).
        cols = {r["name"] for r in con.execute("PRAGMA table_info(monthly_history)")}
        if not cols:
            return 0
        q = (
            "SELECT mh.*, a.platform AS a_platform, a.external_account_id AS a_ext "
            "FROM monthly_history mh JOIN accounts a ON a.id = mh.account_id"
        )
        legacy_rows = con.execute(q).fetchall()
    except sqlite3.OperationalError:
        return 0
    finally:
        con.close()

    for r in legacy_rows:
        acct = Account.query.filter_by(
            platform=r["a_platform"], external_account_id=r["a_ext"]
        ).first()
        if acct is None:
            continue
        mh = MonthlyHistory.query.filter_by(
            account_id=acct.id, year=r["year"], month=r["month"]
        ).first()
        if mh and mh.is_closed:
            continue  # inmutable
        if mh is None:
            mh = MonthlyHistory(account_id=acct.id, year=r["year"], month=r["month"])
            db.session.add(mh)
        mh.client_id = acct.client_id
        mh.platform = acct.platform
        mh.currency = acct.currency
        mh.panel_type_snapshot = _g(r, "client_type_snapshot") or acct.panel_type
        mh.inversion = _g(r, "investment") or 0.0
        mh.monto_venta = _g(r, "sales_value")
        # En ecommerce legacy, el conteo de ventas se guardó en leads_count.
        mh.ventas = _g(r, "leads_count") or _g(r, "sales_count")
        mh.prospectos = _g(r, "leads_count")
        mh.is_closed = bool(_g(r, "is_closed"))
        imported += 1
    db.session.commit()
    return imported


def _g(row, key, default=None):
    try:
        return row[key]
    except (IndexError, KeyError):
        return default


# --------------------------------------------------------------------------- #
# Orquestación
# --------------------------------------------------------------------------- #
def seed_all(verbose=True):
    db.create_all()  # crea tablas faltantes; NUNCA altera columnas existentes
    members = seed_team()
    seed_clients()
    roster, source = get_roster()
    stats = seed_accounts(roster, members)
    snap = _legacy_snapshot()
    hist = import_legacy_monthly_history(snap)
    if verbose:
        print(f"[seed] roster source = {source} ({len(roster)} cuentas)")
        print(f"[seed] accounts: {stats}")
        print(f"[seed] monthly_history importado: {hist} filas")
        print(f"[seed] clientes: {Client.query.count()} · team: {TeamMember.query.count()}")
    return {"roster_source": source, "roster_count": len(roster), "accounts": stats, "history": hist}


def main():
    app = create_app()
    with app.app_context():
        seed_all()


if __name__ == "__main__":
    sys.exit(main())
