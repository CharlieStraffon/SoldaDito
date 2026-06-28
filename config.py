"""Configuración central de DITO. Lee de entorno (.env). Sin literales mágicos."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)

load_dotenv(BASE_DIR / ".env")


def _bool(name: str, default: bool = False) -> bool:
    return str(os.getenv(name, str(default))).strip().lower() in {"1", "true", "yes", "on"}


def _normalize_sqlite_uri(uri: str) -> str:
    """Convierte una ruta sqlite relativa a absoluta bajo BASE_DIR y asegura el dir."""
    prefix = "sqlite:///"
    if uri.startswith(prefix):
        path = uri[len(prefix):]
        if path and not path.startswith("/"):  # relativa
            abs_path = (BASE_DIR / path).resolve()
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            return f"{prefix}{abs_path}"
    return uri


class Config:
    # --- Flask ---
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-change-me")
    ENV = os.getenv("FLASK_ENV", "production")
    DEBUG = ENV == "development"

    # --- DB ---
    SQLALCHEMY_DATABASE_URI = _normalize_sqlite_uri(
        os.getenv("DATABASE_URL", f"sqlite:///{INSTANCE_DIR / 'dito.db'}")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Anthropic (usar `or` para que SET-pero-vacío caiga al default) ---
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    MODEL_TRIAGE = os.getenv("ANTHROPIC_MODEL_TRIAGE") or "claude-haiku-4-5-20251001"
    MODEL_ANALYST = os.getenv("ANTHROPIC_MODEL_ANALYST") or "claude-sonnet-4-6"

    # Google Sheet KPIs (márgenes/objetivos/cierres) — import en fase posterior.
    SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "")

    # --- Google Ads ---
    GOOGLE_ADS_DEVELOPER_TOKEN = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "")
    GOOGLE_ADS_LOGIN_CUSTOMER_ID = os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "")
    GOOGLE_ADS_CLIENT_ID = os.getenv("GOOGLE_ADS_CLIENT_ID", "")
    GOOGLE_ADS_CLIENT_SECRET = os.getenv("GOOGLE_ADS_CLIENT_SECRET", "")
    GOOGLE_ADS_REFRESH_TOKEN = os.getenv("GOOGLE_ADS_REFRESH_TOKEN", "")

    # --- Meta / Facebook Ads ---
    FACEBOOK_ADS_ACCESS_TOKEN = os.getenv("FACEBOOK_ADS_ACCESS_TOKEN", "")
    FACEBOOK_ADS_APP_ID = os.getenv("FACEBOOK_ADS_APP_ID", "")
    FACEBOOK_ADS_APP_SECRET = os.getenv("FACEBOOK_ADS_APP_SECRET", "")
    FACEBOOK_ADS_BUSINESS_ID = os.getenv("FACEBOOK_ADS_BUSINESS_ID", "")
    FACEBOOK_ADS_API_VERSION = os.getenv("FACEBOOK_ADS_API_VERSION", "v21.0")

    # --- Seed fallback ---
    LEGACY_DB_PATH = os.getenv("LEGACY_DB_PATH", "")

    # --- Notificaciones (nombres alineados al .env real) ---
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT") or 587)
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    EMAIL_FROM = os.getenv("EMAIL_FROM", "")
    EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "DITO")
    EMAIL_TO = os.getenv("EMAIL_TO", "")
    EMAIL_DRY_RUN = _bool("EMAIL_DRY_RUN", True)

    @classmethod
    def google_ads_configured(cls) -> bool:
        return all(
            [
                cls.GOOGLE_ADS_DEVELOPER_TOKEN,
                cls.GOOGLE_ADS_CLIENT_ID,
                cls.GOOGLE_ADS_CLIENT_SECRET,
                cls.GOOGLE_ADS_REFRESH_TOKEN,
            ]
        )

    @classmethod
    def facebook_ads_configured(cls) -> bool:
        return bool(cls.FACEBOOK_ADS_ACCESS_TOKEN)
