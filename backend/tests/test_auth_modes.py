from __future__ import annotations

from pathlib import Path

from app import create_app
from app.extensions import db
from app.models import AdminUser
from app.security import hash_password
from app.services.config_service import set_system_defaults


class BaseAuthConfig:
    TESTING = True
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    STORAGE_ROOT = str(Path(__file__).resolve().parents[2] / "storage_test")
    MOBILE_DEFAULT_PASSWORD = "123123"
    CHARGE_MAX_EXECUTE_ROWS = 20
    INVENTORY_LOW_STOCK_THRESHOLD = 50
    SESSION_COOKIE_SECURE = False
    AUTH_MODE = "local"
    AUTH_DISABLED_USERNAME = "external-admin"
    AUTH_PROXY_USER_HEADERS = "X-Remote-User,X-Forwarded-User"
    AUTH_PROXY_REQUIRED_SECRET_HEADER = ""
    AUTH_PROXY_REQUIRED_SECRET = ""


def make_client(config):
    app = create_app(config)
    with app.app_context():
        db.create_all()
        set_system_defaults()
        admin = AdminUser(username="admin", password_hash=hash_password("admin123456"))
        db.session.add(admin)
        db.session.commit()
    return app, app.test_client()


def teardown_app(app):
    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_auth_mode_defaults_to_local_login():
    app, client = make_client(BaseAuthConfig)
    try:
        response = client.get("/api/v1/auth/mode")

        assert response.status_code == 200
        assert response.json["data"]["mode"] == "local"
        assert response.json["data"]["local_login_enabled"] is True
    finally:
        teardown_app(app)


def test_disabled_auth_mode_uses_fixed_audit_user_and_csrf():
    class DisabledConfig(BaseAuthConfig):
        AUTH_MODE = "disabled"
        AUTH_DISABLED_USERNAME = "safeline-admin"

    app, client = make_client(DisabledConfig)
    try:
        me = client.get("/api/v1/auth/me")

        assert me.status_code == 200
        assert me.json["data"]["user"]["username"] == "safeline-admin"
        assert me.json["data"]["csrf_token"]

        update = client.put(
            "/api/v1/config",
            headers={"X-CSRF-Token": me.json["data"]["csrf_token"]},
            json={"integration.syslog.enabled": {"value": True}},
        )
        assert update.status_code == 200
    finally:
        teardown_app(app)


def test_proxy_auth_mode_requires_identity_header_and_auto_creates_user():
    class ProxyConfig(BaseAuthConfig):
        AUTH_MODE = "proxy"

    app, client = make_client(ProxyConfig)
    try:
        anonymous = client.get("/api/v1/auth/me")
        assert anonymous.status_code == 401

        me = client.get("/api/v1/auth/me", headers={"X-Remote-User": "alice@example.test"})
        assert me.status_code == 200
        assert me.json["data"]["user"]["username"] == "alice@example.test"
        assert me.json["data"]["csrf_token"]

        with app.app_context():
            assert AdminUser.query.filter_by(username="alice@example.test").first() is not None
    finally:
        teardown_app(app)


def test_proxy_auth_mode_can_require_shared_secret_header():
    class ProxySecretConfig(BaseAuthConfig):
        AUTH_MODE = "proxy"
        AUTH_PROXY_REQUIRED_SECRET_HEADER = "X-Auth-Proxy-Secret"
        AUTH_PROXY_REQUIRED_SECRET = "shared-secret"

    app, client = make_client(ProxySecretConfig)
    try:
        missing_secret = client.get("/api/v1/auth/me", headers={"X-Remote-User": "bob"})
        assert missing_secret.status_code == 401

        me = client.get(
            "/api/v1/auth/me",
            headers={"X-Remote-User": "bob", "X-Auth-Proxy-Secret": "shared-secret"},
        )
        assert me.status_code == 200
        assert me.json["data"]["user"]["username"] == "bob"
    finally:
        teardown_app(app)


def test_local_password_login_is_disabled_outside_local_mode():
    class ProxyConfig(BaseAuthConfig):
        AUTH_MODE = "proxy"

    app, client = make_client(ProxyConfig)
    try:
        response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123456"})

        assert response.status_code == 409
        assert response.json["code"] == "AUTH409"
    finally:
        teardown_app(app)
