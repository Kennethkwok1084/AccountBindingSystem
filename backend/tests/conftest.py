from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest

from app import create_app
from app.extensions import db
from app.models import AdminUser
from app.security import hash_password
from app.services.config_service import set_system_defaults


class TestConfig:
    TESTING = True
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    STORAGE_ROOT = str(Path(__file__).resolve().parents[2] / "storage_test")
    MOBILE_DEFAULT_PASSWORD = "123123"
    CHARGE_MAX_EXECUTE_ROWS = 20
    INVENTORY_LOW_STOCK_THRESHOLD = 50


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        set_system_defaults()
        admin = AdminUser(username="admin", password_hash=hash_password("admin123456"))
        db.session.add(admin)
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_headers(client):
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123456"})
    assert response.status_code == 200
    csrf_token = response.json["data"]["csrf_token"]
    return {"X-CSRF-Token": csrf_token}


def excel_file(rows):
    buffer = BytesIO()
    pd.DataFrame(rows).to_excel(buffer, index=False)
    buffer.seek(0)
    return buffer

