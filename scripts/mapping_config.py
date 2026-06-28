"""Config curado de la MATRIZ de categorización + tableros STATUS.

Fuente de verdad para: mapeo cuenta->cliente, panel_type EXPLÍCITO, capture_method,
value_source, purpose, fees/tiers/etapas por (cliente x plataforma).

Reglas clave codificadas:
  · panel_type es explícito por cliente (consistente entre plataformas en estos datos).
  · capture_method / value_source pueden diferir por plataforma.
  · Ser Rizada: leads pero value_source=auto_platform (cita pagada on-site).
  · Multi-Encomiendas/Google: calls, valor IGNORADO para ROI (manual_close, sin valor real).
  · Cuenta sin patrón -> pendiente_de_clasificar (NUNCA tipo asumido).

Márgenes conocidos (D2): Ruma .30, SkyHigh .60, CQ .85, Crespos .45. Resto -> 0.35 default.
Fees/tiers/etapas/budgets: de STATUS (Meta/Google boards).
"""
from webapp.constants import (
    CAPTURE_CALLS,
    CAPTURE_CHECKOUT,
    CAPTURE_INSTANT_FORM,
    CAPTURE_MESSAGES,
    CAPTURE_ONSITE_PIXEL,
    PANEL_ECOMMERCE,
    PANEL_LEADS,
    PLATFORM_FACEBOOK_ADS,
    PLATFORM_GOOGLE_ADS,
    STATUS_ACTIVO,
    STATUS_INACTIVO,
    STATUS_PAUSADO,
    TICKET_ESTANDAR,
    TICKET_HIGH,
    TICKET_HIGH_PREMIUM,
    TIER_BAJO,
    TIER_DIAMANTE,
    TIER_IMPORTANTE,
    TIER_INTERMEDIO,
    VALUE_AUTO_PLATFORM,
    VALUE_MANUAL_CLOSE,
)

FB = PLATFORM_FACEBOOK_ADS
GG = PLATFORM_GOOGLE_ADS

TEAM = [
    {"slug": "irving", "name": "Irving", "role": "Meta", "email": "irving@ditoestudio.com",
     "pref": {"channel": "whatsapp+tablero", "cadence": "semanal", "anticipation_days": 7, "low_noise": True}},
    {"slug": "carlos", "name": "Carlos", "role": "Google", "email": "carlos@ditoestudio.com",
     "pref": {"channel": "tablero+correo", "cadence": "tiempo_real", "anticipation_days": 3, "low_noise": False}},
]

# Cada cliente: panel_type explícito + categorización por plataforma + datos STATUS.
# fee/etapa/budget tomados de los tableros STATUS (en MXN salvo nota).
CLIENTS = {
    # --- ECOMMERCE (valor automático del pixel/feed) ---
    "ruma": {
        "name": "RUMA", "business_type": "productos", "ticket_tier": TICKET_ESTANDAR,
        "margin_pct": 0.30, "status": STATUS_ACTIVO,
        "panel_type": PANEL_ECOMMERCE,
        "platforms": {
            FB: {"tier": TIER_IMPORTANTE, "fee": 11000, "etapa": "Estabilización", "budget": 13000,
                 "capture": [CAPTURE_CHECKOUT], "primary": CAPTURE_CHECKOUT, "value_source": VALUE_AUTO_PLATFORM},
            GG: {"tier": TIER_IMPORTANTE, "fee": 11000, "etapa": "ESCALAR", "budget": None,
                 "capture": [CAPTURE_CHECKOUT], "primary": CAPTURE_CHECKOUT, "value_source": VALUE_AUTO_PLATFORM},
        },
    },
    "cch": {
        "name": "CCH", "business_type": "productos", "ticket_tier": TICKET_ESTANDAR,
        "status": STATUS_ACTIVO, "panel_type": PANEL_ECOMMERCE,
        "platforms": {
            FB: {"tier": TIER_BAJO, "fee": 2700, "etapa": "Optimización", "budget": 12500,
                 "capture": [CAPTURE_CHECKOUT], "primary": CAPTURE_CHECKOUT, "value_source": VALUE_AUTO_PLATFORM},
            GG: {"tier": TIER_BAJO, "fee": 2700, "etapa": "Optimización", "budget": None,
                 "capture": [CAPTURE_CHECKOUT], "primary": CAPTURE_CHECKOUT, "value_source": VALUE_AUTO_PLATFORM},
        },
    },
    "skyhigh": {
        "name": "SKYHIGH", "business_type": "servicios", "ticket_tier": TICKET_ESTANDAR,
        "margin_pct": 0.60, "status": STATUS_ACTIVO, "panel_type": PANEL_ECOMMERCE,
        "platforms": {
            FB: {"tier": TIER_IMPORTANTE, "fee": 12000, "etapa": "Estabilización", "budget": 64407.91,
                 "capture": [CAPTURE_CHECKOUT], "primary": CAPTURE_CHECKOUT, "value_source": VALUE_AUTO_PLATFORM},
        },
    },
    "icona": {
        "name": "ICONA", "business_type": "productos", "ticket_tier": TICKET_ESTANDAR,
        "status": STATUS_INACTIVO, "panel_type": PANEL_ECOMMERCE,   # relación terminada
        "platforms": {
            FB: {"tier": TIER_IMPORTANTE, "fee": 14000, "etapa": "TERMINADO", "budget": 8500,
                 "capture": [CAPTURE_CHECKOUT], "primary": CAPTURE_CHECKOUT, "value_source": VALUE_AUTO_PLATFORM},
            GG: {"tier": TIER_IMPORTANTE, "fee": 14000, "etapa": "Pausado", "budget": None,
                 "capture": [CAPTURE_CHECKOUT], "primary": CAPTURE_CHECKOUT, "value_source": VALUE_AUTO_PLATFORM},
        },
    },

    # --- LEADS (valor solo del cierre manual, salvo excepción Ser Rizada) ---
    "ser_rizada": {
        "name": "Ser Rizada", "business_type": "servicios", "ticket_tier": TICKET_ESTANDAR,
        "status": STATUS_ACTIVO, "panel_type": PANEL_LEADS,
        "platforms": {
            # Excepción: leads pero value_source=auto_platform (cita pagada on-site con tracking).
            FB: {"tier": TIER_DIAMANTE, "fee": 0, "etapa": "Optimización", "budget": 10000,
                 "capture": [CAPTURE_ONSITE_PIXEL], "primary": CAPTURE_ONSITE_PIXEL, "value_source": VALUE_AUTO_PLATFORM},
            GG: {"tier": TIER_IMPORTANTE, "fee": 0, "etapa": "Testing", "budget": None,
                 "capture": [CAPTURE_INSTANT_FORM], "primary": CAPTURE_INSTANT_FORM, "value_source": VALUE_MANUAL_CLOSE},
        },
    },
    "celeste": {
        "name": "Celeste", "business_type": "servicios", "ticket_tier": TICKET_ESTANDAR,
        "status": STATUS_ACTIVO, "panel_type": PANEL_LEADS,
        "platforms": {
            FB: {"tier": TIER_BAJO, "fee": 3500, "etapa": "Optimización", "budget": 5000,
                 "capture": [CAPTURE_MESSAGES, CAPTURE_ONSITE_PIXEL], "primary": CAPTURE_MESSAGES, "value_source": VALUE_MANUAL_CLOSE},
        },
    },
    "miriam_robles": {
        "name": "Miriam Robles", "business_type": "servicios", "ticket_tier": TICKET_ESTANDAR,
        "status": STATUS_ACTIVO, "panel_type": PANEL_LEADS,
        "platforms": {
            FB: {"tier": TIER_BAJO, "fee": 4000, "etapa": "Optimización", "budget": 4500,
                 "capture": [CAPTURE_MESSAGES], "primary": CAPTURE_MESSAGES, "value_source": VALUE_MANUAL_CLOSE},
        },
    },
    "multi_encomiendas": {
        "name": "Multi-Encomiendas", "business_type": "servicios", "ticket_tier": TICKET_ESTANDAR,
        "status": STATUS_ACTIVO, "panel_type": PANEL_LEADS, "currency": "USD",
        "platforms": {
            FB: {"tier": TIER_DIAMANTE, "fee": 26500, "etapa": "Optimización", "budget": 90000,
                 "capture": [CAPTURE_MESSAGES], "primary": CAPTURE_MESSAGES, "value_source": VALUE_MANUAL_CLOSE},
            # Google: calls; el "valor" es de referencia y se IGNORA para ROI/ROAS.
            GG: {"tier": TIER_IMPORTANTE, "fee": 26500, "etapa": "Optimización", "budget": None,
                 "capture": [CAPTURE_CALLS], "primary": CAPTURE_CALLS, "value_source": VALUE_MANUAL_CLOSE,
                 "ignore_platform_value": True},
        },
    },
    "adn_gym": {
        "name": "ADN Gym", "business_type": "servicios", "ticket_tier": TICKET_ESTANDAR,
        "status": STATUS_ACTIVO, "panel_type": PANEL_LEADS,
        "platforms": {
            FB: {"tier": TIER_IMPORTANTE, "fee": 15000, "etapa": "Optimización", "budget": 6000,
                 "capture": [CAPTURE_MESSAGES], "primary": CAPTURE_MESSAGES, "value_source": VALUE_MANUAL_CLOSE},
        },
    },
    "gymex": {
        "name": "Gymex", "business_type": "productos", "ticket_tier": TICKET_HIGH,
        "status": STATUS_ACTIVO, "panel_type": PANEL_LEADS,
        "platforms": {
            FB: {"tier": TIER_INTERMEDIO, "fee": 5000, "etapa": "Optimización", "budget": 5000,
                 "capture": [CAPTURE_MESSAGES, CAPTURE_ONSITE_PIXEL], "primary": CAPTURE_MESSAGES, "value_source": VALUE_MANUAL_CLOSE},
            GG: {"tier": TIER_IMPORTANTE, "fee": 6000, "etapa": "Estabilización", "budget": None,
                 "capture": [CAPTURE_CALLS, CAPTURE_ONSITE_PIXEL], "primary": CAPTURE_CALLS, "value_source": VALUE_MANUAL_CLOSE},
        },
    },
    "poliestirenos": {
        "name": "Poliestirenos", "business_type": "productos", "ticket_tier": TICKET_HIGH,
        "status": STATUS_ACTIVO, "panel_type": PANEL_LEADS,
        "platforms": {
            FB: {"tier": TIER_INTERMEDIO, "fee": 8500, "etapa": "Optimización", "budget": 2500,
                 "capture": [CAPTURE_MESSAGES], "primary": CAPTURE_MESSAGES, "value_source": VALUE_MANUAL_CLOSE},
            GG: {"tier": TIER_IMPORTANTE, "fee": 8500, "etapa": "Optimización", "budget": None,
                 "capture": [CAPTURE_CALLS, CAPTURE_ONSITE_PIXEL], "primary": CAPTURE_CALLS, "value_source": VALUE_MANUAL_CLOSE},
        },
    },
    "cq_arcos": {
        "name": "CQ Arcos", "business_type": "servicios", "ticket_tier": TICKET_ESTANDAR,
        "margin_pct": 0.85, "status": STATUS_ACTIVO, "panel_type": PANEL_LEADS,
        "platforms": {
            FB: {"tier": TIER_IMPORTANTE, "fee": 13000, "etapa": "Optimización", "budget": 3000,
                 "capture": [CAPTURE_MESSAGES], "primary": CAPTURE_MESSAGES, "value_source": VALUE_MANUAL_CLOSE},
            GG: {"tier": TIER_INTERMEDIO, "fee": 13000, "etapa": "Optimización", "budget": None,
                 "capture": [CAPTURE_CALLS], "primary": CAPTURE_CALLS, "value_source": VALUE_MANUAL_CLOSE},
        },
    },
    "sprinkler_repair": {
        "name": "Sprinkler Repair", "business_type": "productos", "ticket_tier": TICKET_HIGH,
        "status": STATUS_ACTIVO, "panel_type": PANEL_LEADS, "currency": "USD",
        "platforms": {
            FB: {"tier": TIER_IMPORTANTE, "fee": 8500, "etapa": "Optimización", "budget": 12000,
                 "capture": [CAPTURE_INSTANT_FORM], "primary": CAPTURE_INSTANT_FORM, "value_source": VALUE_MANUAL_CLOSE},
        },
    },
    "tanam": {
        "name": "Tanam", "business_type": "productos", "ticket_tier": TICKET_HIGH,
        "status": STATUS_ACTIVO, "panel_type": PANEL_LEADS, "currency": "USD",
        "platforms": {
            FB: {"tier": TIER_INTERMEDIO, "fee": None, "etapa": "Testing", "budget": 750,
                 "capture": [CAPTURE_INSTANT_FORM], "primary": CAPTURE_INSTANT_FORM, "value_source": VALUE_MANUAL_CLOSE},
        },
    },
    "edimex": {
        "name": "Edimex", "business_type": "productos", "ticket_tier": TICKET_HIGH_PREMIUM,
        "status": STATUS_PAUSADO, "panel_type": PANEL_LEADS,
        "platforms": {
            FB: {"tier": TIER_IMPORTANTE, "fee": 10000, "etapa": "Pausado", "budget": 4500,
                 "capture": [CAPTURE_MESSAGES, CAPTURE_ONSITE_PIXEL], "primary": CAPTURE_MESSAGES, "value_source": VALUE_MANUAL_CLOSE},
            GG: {"tier": TIER_IMPORTANTE, "fee": 10000, "etapa": "Pausado", "budget": None,
                 "capture": [CAPTURE_CALLS], "primary": CAPTURE_CALLS, "value_source": VALUE_MANUAL_CLOSE},
        },
    },

    # --- Conocidos por margen/moneda pero SIN categorización en la matriz ---
    "crespos": {
        "name": "Crespos", "business_type": "ambos", "ticket_tier": TICKET_ESTANDAR,
        "margin_pct": 0.45, "status": STATUS_ACTIVO, "panel_type": None, "currency": "COP",
        "platforms": {},
    },

    # --- Históricos / terminados ---
    "alejandra_figueroa": {
        "name": "Alejandra Figueroa", "status": STATUS_INACTIVO, "panel_type": None,
        "platforms": {FB: {"tier": TIER_INTERMEDIO, "fee": None, "etapa": "TERMINADO", "budget": 4500}},
    },
    "replica_watch_lab": {
        "name": "Replica Watch Lab", "status": STATUS_INACTIVO, "panel_type": None,
        "platforms": {FB: {"etapa": "TERMINADO"}},
    },
}

# Patrones de nombre (sucios, de la API) -> (client_slug, location_label, purpose_override)
# Se evalúan en orden; el primero que casa gana. Match por substring case-insensitive.
# location/purpose None => usa default del cliente.
NAME_PATTERNS = [
    # Multi-ubicación: detectar la sucursal
    (["multi", "encomienda", "houston"], "multi_encomiendas", "Houston", None),
    (["multi", "encomienda", "dallas"], "multi_encomiendas", "Dallas", None),
    (["multi", "encomienda", "austin"], "multi_encomiendas", "Austin", None),
    (["multi", "encomienda", "louisiana"], "multi_encomiendas", "Louisiana", None),
    (["multi", "encomienda"], "multi_encomiendas", None, None),
    (["encomienda"], "multi_encomiendas", None, None),
    # ADN Gym sucursales + vacantes
    (["adn", "vacante"], "adn_gym", None, "vacantes"),
    (["adn", "hiring"], "adn_gym", None, "vacantes"),
    (["adn", "pachuca"], "adn_gym", "Pachuca", None),
    (["adn", "gym"], "adn_gym", None, None),
    (["adn"], "adn_gym", None, None),
    # Vacantes / hiring de otros (purpose override)
    (["gymex", "vacante"], "gymex", None, "vacantes"),
    (["gymex", "hiring"], "gymex", None, "vacantes"),
    (["sprinkler", "hiring"], "sprinkler_repair", None, "vacantes"),
    (["sprinkler", "vacante"], "sprinkler_repair", None, "vacantes"),
    # Resto por keyword principal
    (["ruma"], "ruma", None, None),
    (["cch"], "cch", None, None),
    (["skyhigh"], "skyhigh", None, None),
    (["sky", "high"], "skyhigh", None, None),
    (["icona"], "icona", None, None),
    (["ser", "rizada"], "ser_rizada", None, None),
    (["rizada"], "ser_rizada", None, None),
    (["celeste"], "celeste", None, None),
    (["miriam"], "miriam_robles", None, None),
    (["robles"], "miriam_robles", None, None),
    (["gymex"], "gymex", None, None),
    (["poliestireno"], "poliestirenos", None, None),
    (["cq", "arcos"], "cq_arcos", None, None),
    (["arcos"], "cq_arcos", None, None),
    (["sprinkler"], "sprinkler_repair", None, None),
    (["tanam"], "tanam", None, None),
    (["edimex"], "edimex", None, None),
    (["crespos"], "crespos", None, None),
    (["alejandra"], "alejandra_figueroa", None, None),
    (["figueroa"], "alejandra_figueroa", None, None),
    (["replica"], "replica_watch_lab", None, None),
    # Pausados/inactivos conocidos (no en matriz; status por nombre)
    # Escampa, Irona -> pausado ; Micah's -> inactivo (se manejan abajo)
]

# Cuentas conocidas por estado especial aunque no estén categorizadas.
STATUS_BY_NAME = [
    (["escampa"], STATUS_PAUSADO),
    (["irona"], STATUS_PAUSADO),
    (["micah"], STATUS_INACTIVO),
]
