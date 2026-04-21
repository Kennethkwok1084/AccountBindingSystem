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
    MOBILE_DEFAULT_PASSWORD = "123123"
    SYSTEM_TIMEZONE = os.getenv("TZ", "Asia/Shanghai")
    CHARGE_MAX_EXECUTE_ROWS = int(os.getenv("CHARGE_MAX_EXECUTE_ROWS", "20"))
    INVENTORY_LOW_STOCK_THRESHOLD = int(os.getenv("INVENTORY_LOW_STOCK_THRESHOLD", "50"))
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH_MB", "64")) * 1024 * 1024
    DEFAULT_ADMIN_USERNAME = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
    DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "")
