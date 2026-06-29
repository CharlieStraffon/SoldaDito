"""Modelo de datos DITO (ADR-002). Esquema fresco — el histórico entra por seed.

Jerarquía:  TeamMember -> Client -> Account -> (Campaign -> CampaignMetric)
con MonthlyHistory, MonthlyTarget, AccountBaseline, MeasurementProfile,
Alert, ActionLog y NotificationPreference.

Regla: panel_type es EXPLÍCITO (sembrado de la matriz), nunca derivado del
evento de conversión. El origen de cada dato se rastrea con sufijos *_source
donde aplica (API / manual / calculado / config).
"""
from datetime import datetime

from sqlalchemy import UniqueConstraint

from .constants import (
    DEFAULT_MARGIN_PCT,
    PURPOSE_SALES_LEADS,
    STATUS_ACTIVO,
)
from .database import db


def _utcnow():
    return datetime.utcnow()


# --------------------------------------------------------------------------- #
# Equipo y ruteo
# --------------------------------------------------------------------------- #
class TeamMember(db.Model):
    __tablename__ = "team_members"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(200), unique=True)
    role = db.Column(db.String(80))            # p.ej. "Meta" (Irving) / "Google" (Carlos)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow)

    preference = db.relationship(
        "NotificationPreference", back_populates="member",
        uselist=False, cascade="all, delete-orphan",
    )
    accounts = db.relationship("Account", back_populates="assignee")

    def __repr__(self):
        return f"<TeamMember {self.slug}>"


class NotificationPreference(db.Model):
    __tablename__ = "notification_preferences"

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey("team_members.id"), unique=True, nullable=False)
    channel = db.Column(db.String(120))         # "whatsapp+tablero" / "tablero+correo"
    cadence = db.Column(db.String(40))          # "semanal" / "tiempo_real"
    anticipation_days = db.Column(db.Integer)   # Irving 7 · Carlos 3
    low_noise = db.Column(db.Boolean, default=False)
    thresholds = db.Column(db.JSON)             # overrides por métrica (opcional)

    member = db.relationship("TeamMember", back_populates="preference")


# --------------------------------------------------------------------------- #
# Cliente
# --------------------------------------------------------------------------- #
class Client(db.Model):
    __tablename__ = "clients"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False)

    business_type = db.Column(db.String(40))        # productos/servicios/ambos (etiqueta CRM, NO decide panel)
    ticket_tier = db.Column(db.String(40))          # estandar/high_ticket/high_premium
    commercial_tier = db.Column(db.String(40))      # Diamante/Importante/Intermedio/Bajo
    industry = db.Column(db.String(120))
    status = db.Column(db.String(40), default=STATUS_ACTIVO)  # activo/pausado/inactivo/baja

    # Margen editable — vive AQUÍ. Default 0.35. Nunca hardcodear en cálculo.
    margin_pct = db.Column(db.Float, default=DEFAULT_MARGIN_PCT)
    margin_pct_source = db.Column(db.String(20), default="config")

    # Fee a nivel cliente; el fee por (cliente x plataforma) puede afinarse por engagement.
    monthly_fee = db.Column(db.Float)
    fee_currency = db.Column(db.String(10), default="MXN")

    client_type_override = db.Column(db.String(40))  # aplica a todas sus cuentas (raro)

    # contacto / administrativos
    contact_name = db.Column(db.String(200))
    website = db.Column(db.String(300))
    notion_url = db.Column(db.String(400))

    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)

    accounts = db.relationship("Account", back_populates="client")

    def effective_margin(self):
        return self.margin_pct if self.margin_pct is not None else DEFAULT_MARGIN_PCT

    def __repr__(self):
        return f"<Client {self.slug}>"


# --------------------------------------------------------------------------- #
# Cuenta (engagement = cliente x plataforma se calcula sumando cuentas)
# --------------------------------------------------------------------------- #
class Account(db.Model):
    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("platform", "external_account_id", name="uq_account_platform_extid"),
    )

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"))

    # --- API (read-only) ---
    platform = db.Column(db.String(20), nullable=False)        # google_ads / facebook_ads
    external_account_id = db.Column(db.String(120), nullable=False)
    name = db.Column(db.String(300))
    currency = db.Column(db.String(10), default="MXN")         # de la API, nunca se mezcla
    account_status = db.Column(db.String(40))                  # ACTIVE/ENABLED/SUSPENDED...
    account_status_reason = db.Column(db.String(200))
    conversion_category = db.Column(db.String(40))             # sugerencia de seed, NO fuente en runtime

    # --- SEED (matriz) — categorización EXPLÍCITA ---
    panel_type = db.Column(db.String(20))                      # ecommerce / leads (None => pendiente)
    capture_methods = db.Column(db.JSON, default=list)         # lista multivalor
    primary_capture_method = db.Column(db.String(40))
    value_source = db.Column(db.String(40))                    # auto_platform / manual_close
    purpose = db.Column(db.String(40), default=PURPOSE_SALES_LEADS)  # ventas_leads / vacantes
    location_label = db.Column(db.String(120))                 # Houston/Dallas/Pachuca...

    # Override visual del panel/objetivo (ecommerce/leads/mensajes) — selector del desglose.
    client_type_override = db.Column(db.String(20))

    # --- Estado de relación (gestión) ---
    status = db.Column(db.String(40), default=STATUS_ACTIVO)   # activo/pausado/inactivo/baja/pendiente_de_clasificar
    is_active = db.Column(db.Boolean, default=True)

    # --- SEED operativo ---
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("team_members.id"))
    commercial_tier = db.Column(db.String(40))
    etapa = db.Column(db.String(60))                           # Optimización/Estabilización/Pausado...
    target_cpa = db.Column(db.Float)
    target_roas = db.Column(db.Float)
    monthly_budget = db.Column(db.Float)
    monthly_fee = db.Column(db.Float)                          # honorarios del engagement (cliente x plataforma)

    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)

    client = db.relationship("Client", back_populates="accounts")
    assignee = db.relationship("TeamMember", back_populates="accounts")
    measurement = db.relationship(
        "MeasurementProfile", back_populates="account",
        uselist=False, cascade="all, delete-orphan",
    )
    campaigns = db.relationship("Campaign", back_populates="account", cascade="all, delete-orphan")

    @property
    def is_classified(self):
        return self.panel_type is not None

    @property
    def is_vacantes(self):
        from .constants import PURPOSE_VACANTES
        return self.purpose == PURPOSE_VACANTES

    def __repr__(self):
        return f"<Account {self.platform}:{self.external_account_id} {self.name!r}>"


class MeasurementProfile(db.Model):
    """Perfil de medición por cuenta (1:1). offline_import=NO en leads => bandera de riesgo."""
    __tablename__ = "measurement_profiles"

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), unique=True, nullable=False)

    pixel_ok = db.Column(db.Boolean)
    capi_ok = db.Column(db.Boolean)
    ga4_linked = db.Column(db.Boolean)
    enhanced_conversions = db.Column(db.Boolean)
    offline_import = db.Column(db.Boolean)        # hoy = NO en leads
    primary_conversion_label = db.Column(db.String(120))
    domain_verified = db.Column(db.Boolean)
    consent_mode = db.Column(db.Boolean)
    last_verified_at = db.Column(db.DateTime)
    last_verified_by = db.Column(db.Integer, db.ForeignKey("team_members.id"))

    account = db.relationship("Account", back_populates="measurement")


# --------------------------------------------------------------------------- #
# Campañas y métricas diarias (PORT del sync probado)
# --------------------------------------------------------------------------- #
class Campaign(db.Model):
    __tablename__ = "campaigns"
    __table_args__ = (
        UniqueConstraint("platform", "external_campaign_id", name="uq_campaign_platform_extid"),
    )

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False)
    platform = db.Column(db.String(20), nullable=False)
    external_campaign_id = db.Column(db.String(120), nullable=False)
    name = db.Column(db.String(400))
    campaign_type = db.Column(db.String(60))      # SEARCH/SHOPPING/PMAX | SALES/LEADS/MESSAGES...
    status = db.Column(db.String(40))
    bidding_strategy_type = db.Column(db.String(60))   # Google only
    daily_budget = db.Column(db.Float)

    account = db.relationship("Account", back_populates="campaigns")
    metrics = db.relationship("CampaignMetric", back_populates="campaign", cascade="all, delete-orphan")


class CampaignMetric(db.Model):
    __tablename__ = "campaign_metrics"
    __table_args__ = (
        UniqueConstraint("campaign_id", "date", name="uq_metric_campaign_date"),
    )

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey("campaigns.id"), nullable=False)
    platform = db.Column(db.String(20), nullable=False)
    date = db.Column(db.Date, nullable=False)

    # base (ambas plataformas)
    impressions = db.Column(db.Integer, default=0)
    clicks = db.Column(db.Integer, default=0)
    cost = db.Column(db.Float, default=0.0)             # en moneda nativa de la cuenta
    conversions = db.Column(db.Float, default=0.0)      # del objetivo primario
    conversion_value = db.Column(db.Float, default=0.0)
    ctr = db.Column(db.Float, default=0.0)
    conversion_rate = db.Column(db.Float, default=0.0)

    # Facebook extras (Google = 0)
    reach = db.Column(db.Integer, default=0)
    frequency = db.Column(db.Float, default=0.0)
    link_clicks = db.Column(db.Float, default=0.0)
    unique_link_clicks = db.Column(db.Float, default=0.0)
    thruplays = db.Column(db.Float, default=0.0)
    purchases = db.Column(db.Float, default=0.0)
    purchases_value = db.Column(db.Float, default=0.0)
    leads = db.Column(db.Float, default=0.0)
    leads_value = db.Column(db.Float, default=0.0)
    messages = db.Column(db.Float, default=0.0)
    add_to_cart = db.Column(db.Float, default=0.0)
    initiate_checkout = db.Column(db.Float, default=0.0)
    add_payment_info = db.Column(db.Float, default=0.0)

    # Google extras
    search_budget_lost_impression_share = db.Column(db.Float, default=0.0)
    search_rank_lost_impression_share = db.Column(db.Float, default=0.0)

    campaign = db.relationship("Campaign", back_populates="metrics")


# --------------------------------------------------------------------------- #
# Desglose mensual (cuenta-mes) — motor financiero
# --------------------------------------------------------------------------- #
class MonthlyHistory(db.Model):
    __tablename__ = "monthly_history"
    __table_args__ = (
        UniqueConstraint("account_id", "year", "month", name="uq_monthly_account_period"),
    )

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"))
    platform = db.Column(db.String(20), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(10), default="MXN")

    panel_type_snapshot = db.Column(db.String(20))     # congela el tipo del momento

    # --- Comunes ---
    inversion = db.Column(db.Float, default=0.0)       # API
    inversion_source = db.Column(db.String(20), default="api")
    ventas_totales = db.Column(db.Float)               # MANUAL, opcional (para %anuncios)

    # --- ecommerce (API/pixel) ---
    clics = db.Column(db.Float)
    add_to_carts = db.Column(db.Float)
    checkouts = db.Column(db.Float)

    # --- resultado primario por tipo ---
    prospectos = db.Column(db.Float)                   # leads: API · etiqueta según capture
    ventas = db.Column(db.Float)                       # ecommerce: API · leads: manual (ventas_concretadas)
    ventas_source = db.Column(db.String(20))
    monto_venta = db.Column(db.Float)                  # ecommerce: API · leads: manual
    monto_source = db.Column(db.String(20))

    # --- Snapshots de cierre (congelados) ---
    margin_pct_snapshot = db.Column(db.Float)
    fee_snapshot = db.Column(db.Float)

    # --- Calculados (cuenta-mes; se recalculan mientras abierto) ---
    cpl = db.Column(db.Float)
    cpa = db.Column(db.Float)
    roas = db.Column(db.Float)
    aov = db.Column(db.Float)
    conv_pct = db.Column(db.Float)
    cpv = db.Column(db.Float)                           # vacantes
    utilidad_antes_honorarios = db.Column(db.Float)

    is_closed = db.Column(db.Boolean, default=False)
    closed_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)

    account = db.relationship("Account")

    def __repr__(self):
        return f"<MonthlyHistory acct={self.account_id} {self.year}-{self.month:02d} closed={self.is_closed}>"


class MonthlyTarget(db.Model):
    __tablename__ = "monthly_targets"
    __table_args__ = (
        UniqueConstraint("account_id", "year", "month", "metric", name="uq_target_account_period_metric"),
    )

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    metric = db.Column(db.String(40), nullable=False)   # spend/cpa/roas/results/aov
    objetivo = db.Column(db.Float)
    logrado = db.Column(db.Float)
    variacion_pct = db.Column(db.Float)
    estatus = db.Column(db.String(20))                  # Excelente/Bien/Medio/Mal/Pésimo

    account = db.relationship("Account")


class AccountBaseline(db.Model):
    """"Tu normal": referencia congelada por cuenta x métrica sobre meses cerrados."""
    __tablename__ = "account_baselines"
    __table_args__ = (
        UniqueConstraint("account_id", "metric", "window_days", name="uq_baseline_account_metric_window"),
    )

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False)
    platform = db.Column(db.String(20))
    metric = db.Column(db.String(40), nullable=False)   # cpa/cpl/roas/cost_per_result/spend...
    window_days = db.Column(db.Integer, default=90)     # 30 / 90

    normal_value = db.Column(db.Float)                  # mediana (robusta)
    dispersion = db.Column(db.Float)                    # IQR o sigma (para z-score Meta)
    sample_size = db.Column(db.Integer)
    last_closed_period = db.Column(db.String(10))       # "YYYY-MM"
    computed_at = db.Column(db.DateTime, default=_utcnow)

    account = db.relationship("Account")


# --------------------------------------------------------------------------- #
# Alertas y registro de acciones
# --------------------------------------------------------------------------- #
class Alert(db.Model):
    __tablename__ = "alerts"
    __table_args__ = (
        UniqueConstraint("account_id", "date", "kind", name="uq_alert_account_date_kind"),
    )

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False)
    platform = db.Column(db.String(20))
    date = db.Column(db.Date, nullable=False)
    kind = db.Column(db.String(60), nullable=False)     # cpa_spike/roas_drop/account_silent...
    metric = db.Column(db.String(40))
    severity = db.Column(db.String(20))                 # critico/rendimiento/positivo
    status = db.Column(db.String(20), default="new")    # new/acknowledged/resolved

    observed_value = db.Column(db.Float)
    normal_value = db.Column(db.Float)
    delta_pct = db.Column(db.Float)
    days_sustained = db.Column(db.Integer, default=1)

    message = db.Column(db.Text)
    ai_explanation = db.Column(db.Text)                 # Haiku, cacheada
    routed_to_id = db.Column(db.Integer, db.ForeignKey("team_members.id"))
    pushed = db.Column(db.Boolean, default=False)       # día 1: solo críticas se empujan

    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)

    account = db.relationship("Account")
    routed_to = db.relationship("TeamMember")


class ActionLog(db.Model):
    """Append-only. El cruce acción <-> resultado (histórico que hoy se pierde)."""
    __tablename__ = "action_log"

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False)
    at = db.Column(db.DateTime, default=_utcnow)
    by_id = db.Column(db.Integer, db.ForeignKey("team_members.id"))
    action_type = db.Column(db.String(40), nullable=False)
    old_value = db.Column(db.String(200))
    new_value = db.Column(db.String(200))
    note = db.Column(db.Text)

    account = db.relationship("Account")
    by = db.relationship("TeamMember")
