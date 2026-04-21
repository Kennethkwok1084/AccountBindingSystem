from __future__ import annotations

from flask import session

from .extensions import db
from .models import AdminUser


def current_user() -> AdminUser | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(AdminUser, user_id)
