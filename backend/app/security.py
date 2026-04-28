from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from functools import wraps

from flask import request, session

try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError
except ImportError:  # pragma: no cover - explicit fallback path
    PasswordHasher = None
    VerifyMismatchError = Exception


_PASSWORD_HASHER = PasswordHasher() if PasswordHasher is not None else None


def hash_password(password: str) -> str:
    if _PASSWORD_HASHER is not None:
        return f"argon2id${_PASSWORD_HASHER.hash(password)}"
    salt = os.urandom(16)
    hashed = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${hashed.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    if password_hash.startswith("argon2id$") and _PASSWORD_HASHER is not None:
        try:
            return _PASSWORD_HASHER.verify(password_hash.removeprefix("argon2id$"), password)
        except VerifyMismatchError:
            return False
    try:
        algo, salt_hex, digest_hex = password_hash.split("$", 2)
    except ValueError:
        return False
    if algo != "scrypt":
        return False
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=bytes.fromhex(salt_hex),
        n=2**14,
        r=8,
        p=1,
    )
    return hmac.compare_digest(derived.hex(), digest_hex)


def generate_csrf_token() -> str:
    token = secrets.token_urlsafe(32)
    session["csrf_token"] = token
    return token


def get_or_create_csrf_token() -> str:
    return session.get("csrf_token") or generate_csrf_token()


def require_session(func):
    from .auth import current_user
    from .responses import error

    @wraps(func)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            return error("AUTH401", "未登录或会话已失效", status=401)
        return func(*args, **kwargs)

    return wrapper


def require_csrf(func):
    from .responses import error

    @wraps(func)
    def wrapper(*args, **kwargs):
        header_token = request.headers.get("X-CSRF-Token", "")
        session_token = session.get("csrf_token", "")
        if not header_token or not session_token or not hmac.compare_digest(header_token, session_token):
            return error("AUTH403", "CSRF 校验失败", status=403)
        return func(*args, **kwargs)

    return wrapper
