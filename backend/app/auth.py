from __future__ import annotations

import hmac
import secrets

from flask import current_app, request, session

from .extensions import db
from .models import AdminUser
from .security import hash_password


AUTH_MODE_LOCAL = "local"
AUTH_MODE_PROXY = "proxy"
AUTH_MODE_DISABLED = "disabled"
AUTH_MODES = {AUTH_MODE_LOCAL, AUTH_MODE_PROXY, AUTH_MODE_DISABLED}


def get_auth_mode() -> str:
    mode = str(current_app.config.get("AUTH_MODE", AUTH_MODE_LOCAL)).strip().lower()
    if mode not in AUTH_MODES:
        current_app.logger.warning("Unknown AUTH_MODE=%s, falling back to local", mode)
        return AUTH_MODE_LOCAL
    return mode


def is_local_login_enabled() -> bool:
    return get_auth_mode() == AUTH_MODE_LOCAL


def _session_user() -> AdminUser | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    user = db.session.get(AdminUser, user_id)
    if user is None or not user.is_active:
        return None
    return user


def _configured_headers() -> list[str]:
    raw_headers = str(current_app.config.get("AUTH_PROXY_USER_HEADERS", ""))
    return [header.strip() for header in raw_headers.split(",") if header.strip()]


def _proxy_secret_matches() -> bool:
    required_secret = str(current_app.config.get("AUTH_PROXY_REQUIRED_SECRET", "") or "")
    if not required_secret:
        return True
    header_name = str(current_app.config.get("AUTH_PROXY_REQUIRED_SECRET_HEADER", "") or "")
    if not header_name:
        return False
    incoming_secret = request.headers.get(header_name, "")
    return bool(incoming_secret) and hmac.compare_digest(incoming_secret, required_secret)


def _proxy_username() -> str | None:
    if not _proxy_secret_matches():
        return None
    for header_name in _configured_headers():
        value = request.headers.get(header_name, "").strip()
        if value:
            return value[:255]
    return None


def _get_or_create_admin(username: str) -> AdminUser | None:
    user = AdminUser.query.filter_by(username=username).first()
    if user is not None:
        return user if user.is_active else None

    random_password = secrets.token_urlsafe(32)
    user = AdminUser(username=username, password_hash=hash_password(random_password), is_active=True)
    db.session.add(user)
    db.session.commit()
    current_app.logger.info("Auto-created admin user for external identity: %s", username)
    return user


def current_user() -> AdminUser | None:
    mode = get_auth_mode()
    if mode == AUTH_MODE_LOCAL:
        return _session_user()
    if mode == AUTH_MODE_DISABLED:
        username = str(current_app.config.get("AUTH_DISABLED_USERNAME", "external-admin")).strip()
        return _get_or_create_admin(username or "external-admin")

    username = _proxy_username()
    if not username:
        return None
    return _get_or_create_admin(username)
