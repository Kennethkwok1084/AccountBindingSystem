from __future__ import annotations

from flask import Blueprint, request, session

from ..auth import current_user
from ..extensions import db
from ..models import AdminUser
from ..responses import error, success
from ..security import generate_csrf_token, hash_password, require_csrf, require_session, verify_password
from ..services.audit_service import write_audit
from ..services.date_service import utcnow


bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.post("/login")
def login():
    payload = request.get_json(silent=True) or {}
    username = payload.get("username", "")
    password = payload.get("password", "")
    user = AdminUser.query.filter_by(username=username, is_active=True).first()
    if user is None or not verify_password(password, user.password_hash):
        return error("AUTH401", "用户名或密码错误", status=401)
    session["user_id"] = user.id
    csrf_token = generate_csrf_token()
    user.last_login_at = utcnow()
    db.session.commit()
    write_audit("login", "admin_user", str(user.id))
    db.session.commit()
    return success({"user": {"id": user.id, "username": user.username}, "csrf_token": csrf_token})


@bp.post("/logout")
@require_session
@require_csrf
def logout():
    user = current_user()
    session.clear()
    write_audit("logout", "admin_user", str(user.id if user else ""))
    db.session.commit()
    return success()


@bp.get("/me")
@require_session
def me():
    user = current_user()
    return success({"user": {"id": user.id, "username": user.username}, "csrf_token": session.get("csrf_token")})


@bp.put("/password")
@require_session
@require_csrf
def change_password():
    payload = request.get_json(silent=True) or {}
    user = current_user()
    if not verify_password(payload.get("old_password", ""), user.password_hash):
        return error("AUTH422", "原密码错误", status=422)
    user.password_hash = hash_password(payload.get("new_password", ""))
    write_audit("change_password", "admin_user", str(user.id))
    db.session.commit()
    return success()
