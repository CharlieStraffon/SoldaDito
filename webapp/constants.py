"""Constantes de dominio. Regla dura: nunca literales de plataforma en el código."""

# --- Plataformas (nunca se suman entre sí) ---
PLATFORM_GOOGLE_ADS = "google_ads"
PLATFORM_FACEBOOK_ADS = "facebook_ads"
PLATFORMS = (PLATFORM_GOOGLE_ADS, PLATFORM_FACEBOOK_ADS)

PLATFORM_LABELS = {
    PLATFORM_GOOGLE_ADS: "Google Ads",
    PLATFORM_FACEBOOK_ADS: "Meta Ads",
}

# --- Tipo de panel (EXPLÍCITO, sembrado de la matriz — nunca derivado del evento) ---
PANEL_ECOMMERCE = "ecommerce"
PANEL_LEADS = "leads"
PANEL_TYPES = (PANEL_ECOMMERCE, PANEL_LEADS)

# --- Métodos de captura (multivalor por cuenta; uno marcado primary) ---
CAPTURE_CHECKOUT = "checkout"
CAPTURE_ONSITE_PIXEL = "onsite_pixel"
CAPTURE_INSTANT_FORM = "instant_form"
CAPTURE_MESSAGES = "messages"
CAPTURE_CALLS = "calls"
CAPTURE_JOB_APPLICATIONS = "job_applications"
CAPTURE_METHODS = (
    CAPTURE_CHECKOUT,
    CAPTURE_ONSITE_PIXEL,
    CAPTURE_INSTANT_FORM,
    CAPTURE_MESSAGES,
    CAPTURE_CALLS,
    CAPTURE_JOB_APPLICATIONS,
)

# Etiqueta de "resultado" para el héroe del panel, por método de captura primario.
CAPTURE_RESULT_LABEL = {
    CAPTURE_CHECKOUT: "compra",
    CAPTURE_ONSITE_PIXEL: "lead en sitio",
    CAPTURE_INSTANT_FORM: "lead",
    CAPTURE_MESSAGES: "conversación",
    CAPTURE_CALLS: "llamada",
    CAPTURE_JOB_APPLICATIONS: "aplicación",
}
CAPTURE_COST_LABEL = {
    CAPTURE_CHECKOUT: "CPA",
    CAPTURE_ONSITE_PIXEL: "costo/lead",
    CAPTURE_INSTANT_FORM: "costo/lead",
    CAPTURE_MESSAGES: "costo/conversación",
    CAPTURE_CALLS: "costo/llamada",
    CAPTURE_JOB_APPLICATIONS: "CPV",
}

# --- Origen del valor (cierre manual vs plataforma) ---
VALUE_AUTO_PLATFORM = "auto_platform"   # pixel/feed
VALUE_MANUAL_CLOSE = "manual_close"     # solo del cierre del equipo
VALUE_SOURCES = (VALUE_AUTO_PLATFORM, VALUE_MANUAL_CLOSE)

# --- Propósito de la cuenta ---
PURPOSE_SALES_LEADS = "ventas_leads"
PURPOSE_VACANTES = "vacantes"           # mide CPV, sin ROI
PURPOSES = (PURPOSE_SALES_LEADS, PURPOSE_VACANTES)

# --- Estado del cliente / relación ---
STATUS_ACTIVO = "activo"
STATUS_PAUSADO = "pausado"
STATUS_INACTIVO = "inactivo"
STATUS_BAJA = "baja"
STATUS_PENDIENTE = "pendiente_de_clasificar"   # cuenta de API sin mapeo
CLIENT_STATUSES = (STATUS_ACTIVO, STATUS_PAUSADO, STATUS_INACTIVO, STATUS_BAJA)

# --- Tier comercial (atención/prioridad — de STATUS) ---
TIER_DIAMANTE = "Diamante"
TIER_IMPORTANTE = "Importante"
TIER_INTERMEDIO = "Intermedio"
TIER_BAJO = "Bajo"
COMMERCIAL_TIERS = (TIER_DIAMANTE, TIER_IMPORTANTE, TIER_INTERMEDIO, TIER_BAJO)

# --- Ticket tier (por cliente) ---
TICKET_ESTANDAR = "estandar"
TICKET_HIGH = "high_ticket"
TICKET_HIGH_PREMIUM = "high_premium"
TICKET_TIERS = (TICKET_ESTANDAR, TICKET_HIGH, TICKET_HIGH_PREMIUM)

# --- Cuentas saludables (visibles en operación diaria) ---
HEALTHY_ACCOUNT_STATUSES = {"ACTIVE", "ENABLED"}

# --- Margen por defecto (editable en Client.margin_pct — NUNCA hardcodear en cálculo) ---
DEFAULT_MARGIN_PCT = 0.35

# --- Alertas ---
SEVERITY_CRITICAL = "critico"
SEVERITY_PERFORMANCE = "rendimiento"
SEVERITY_POSITIVE = "positivo"
SEVERITIES = (SEVERITY_CRITICAL, SEVERITY_PERFORMANCE, SEVERITY_POSITIVE)

ALERT_NEW = "new"
ALERT_ACKNOWLEDGED = "acknowledged"
ALERT_RESOLVED = "resolved"

# --- Ventana de re-escritura de Google (atribución tardía). NO reducir. ---
GOOGLE_CATCHUP_REFRESH_DAYS = 3
CATCHUP_MAX_GAP_DAYS = 30
BACKFILL_CHUNK_DAYS = 30

# --- Tipos de acción del ActionLog ---
ACTION_BUDGET_CHANGE = "budget_change"
ACTION_PAUSE = "pause"
ACTION_ACTIVATE = "activate"
ACTION_NEW_CREATIVE = "new_creative"
ACTION_BID_CHANGE = "bid_change"
ACTION_AUDIENCE_CHANGE = "audience_change"
ACTION_COPY_CHANGE = "copy_change"
ACTION_HYPOTHESIS = "hypothesis"
ACTION_TYPES = (
    ACTION_BUDGET_CHANGE,
    ACTION_PAUSE,
    ACTION_ACTIVATE,
    ACTION_NEW_CREATIVE,
    ACTION_BID_CHANGE,
    ACTION_AUDIENCE_CHANGE,
    ACTION_COPY_CHANGE,
    ACTION_HYPOTHESIS,
)
