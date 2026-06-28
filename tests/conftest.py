"""Fixtures de test: app con DB temporal fresca."""
import os
import tempfile

import pytest

from config import Config
from webapp import create_app
from webapp.database import db as _db


class TestConfig(Config):
    TESTING = True
    ENV = "development"
    DEBUG = True
    LEGACY_DB_PATH = ""  # tests no dependen del legacy


@pytest.fixture()
def app():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    TestConfig.SQLALCHEMY_DATABASE_URI = f"sqlite:///{path}"
    app = create_app(TestConfig)
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
    os.unlink(path)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def session(app):
    with app.app_context():
        yield _db.session
