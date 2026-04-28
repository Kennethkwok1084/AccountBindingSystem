from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'storage' / 'dev.sqlite3'}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_AS_ASCII = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    STORAGE_ROOT = os.getenv("STORAGE_ROOT", str(BASE_DIR / "storage"))
    BATCH_MODIFY_TEMPLATE_PATH = os.getenv(
        "BATCH_MODIFY_TEMPLATE_PATH",
        str(BASE_DIR / "批量修改资料模版.xls"),
    )
    MOBILE_DEFAULT_PASSWORD = "123123"
    SYSTEM_TIMEZONE = os.getenv("TZ", "Asia/Shanghai")
    CHARGE_MAX_EXECUTE_ROWS = int(os.getenv("CHARGE_MAX_EXECUTE_ROWS", "20"))
    INVENTORY_LOW_STOCK_THRESHOLD = int(os.getenv("INVENTORY_LOW_STOCK_THRESHOLD", "50"))
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH_MB", "64")) * 1024 * 1024
    DEFAULT_ADMIN_USERNAME = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
    DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "")
    AUTH_MODE = os.getenv("AUTH_MODE", "local")
    AUTH_DISABLED_USERNAME = os.getenv("AUTH_DISABLED_USERNAME", "external-admin")
    AUTH_PROXY_USER_HEADERS = os.getenv(
        "AUTH_PROXY_USER_HEADERS",
        "X-Remote-User,X-Forwarded-User,Remote-User,X-Auth-Request-User",
    )
    AUTH_PROXY_REQUIRED_SECRET_HEADER = os.getenv("AUTH_PROXY_REQUIRED_SECRET_HEADER", "")
    AUTH_PROXY_REQUIRED_SECRET = os.getenv("AUTH_PROXY_REQUIRED_SECRET", "")
