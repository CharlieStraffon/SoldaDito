"""App factory de DITO. Route -> Service -> Client (las rutas nunca llaman a la API directo)."""
from flask import Flask

from config import Config

from .constants import (
    PLATFORM_FACEBOOK_ADS,
    PLATFORM_GOOGLE_ADS,
    PLATFORM_LABELS,
    PLATFORMS,
)
from .csrf import generate_csrf_token
from .database import db


def create_app(config_object=Config):
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(config_object)

    db.init_app(app)

    # Flask-Migrate (Alembic) para cambios incrementales futuros.
    try:
        from flask_migrate import Migrate
        Migrate(app, db, render_as_batch=True)  # batch = ALTER seguro en SQLite
    except Exception:  # pragma: no cover - migrate es opcional para boot
        pass

    # CSRF token disponible en todas las plantillas.
    app.jinja_env.globals["csrf_token"] = generate_csrf_token
    app.jinja_env.globals["PLATFORMS"] = PLATFORMS
    app.jinja_env.globals["PLATFORM_LABELS"] = PLATFORM_LABELS
    app.jinja_env.globals["PLATFORM_GOOGLE_ADS"] = PLATFORM_GOOGLE_ADS
    app.jinja_env.globals["PLATFORM_FACEBOOK_ADS"] = PLATFORM_FACEBOOK_ADS

    _register_filters(app)

    _register_blueprints(app)

    return app


def _register_filters(app):
    """Filtros de presentación. Un número nunca sin contexto (formato consistente)."""

    @app.template_filter("money")
    def money(v, currency=""):
        if v is None:
            return "—"
        s = f"{v:,.2f}"
        return f"{s} {currency}".strip()

    @app.template_filter("num")
    def num(v, dec=0):
        if v is None:
            return "—"
        return f"{v:,.{dec}f}"

    @app.template_filter("ratio")
    def ratio(v):
        if v is None:
            return "—"
        return f"{v:,.2f}×"

    @app.template_filter("pctf")
    def pctf(v, dec=2):
        if v is None:
            return "—"
        return f"{v:.{dec}f}%"

    @app.template_filter("signed_pct")
    def signed_pct(v, dec=1):
        if v is None:
            return "—"
        sign = "+" if v > 0 else ""
        return f"{sign}{v:.{dec}f}%"


def _register_blueprints(app):
    from .routes.health import health_bp
    app.register_blueprint(health_bp)

    # Los siguientes se llenan por fase (dashboard F3, desglose F4, etc.)
    from .routes.dashboard import dashboard_bp
    from .routes.accounts import accounts_bp
    from .routes.history import history_bp
    from .routes.alerts import alerts_bp
    from .routes.actions import actions_bp
    from .routes.admin import admin_bp
    from .routes.reports import reports_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(actions_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(reports_bp)
