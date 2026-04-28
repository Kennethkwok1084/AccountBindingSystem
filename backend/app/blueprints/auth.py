from __future__ import annotations

from flask import Blueprint, request, session

from ..auth import current_user, get_auth_mode, is_local_login_enabled
from ..extensions import db
from ..models import AdminUser
from ..responses import error, success
from ..security import generate_csrf_token, get_or_create_csrf_token, hash_password, require_csrf, require_session, verify_password
from ..services.audit_service import write_audit
from ..services.date_service import utcnow


bp = Blueprint("auth", __name__, url_prefix="/auth")


def _serialize_user(user: AdminUser) -> dict:
    return {"id": user.id, "username": user.username}


@bp.get("/mode")
def mode():
    auth_mode = get_auth_mode()
    return success(
        {
            "mode": auth_mode,
            "local_login_enabled": auth_mode == "local",
            "logout_supported": auth_mode == "local",
        }
    )


@bp.post("/login")
def login():
    if not is_local_login_enabled():
        return error("AUTH409", "当前已关闭本地账号密码登录", status=409)
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
    return success({"user": _serialize_user(user), "csrf_token": csrf_token, "auth_mode": get_auth_mode()})


@bp.post("/logout")
@require_session
@require_csrf
def logout():
    user = current_user()
    session.clear()
    write_audit("logout", "admin_user", str(user.id if user else ""), operator_id=user.id if user else None)
    db.session.commit()
    return success()


@bp.get("/me")
@require_session
def me():
    user = current_user()
    return success({"user": _serialize_user(user), "csrf_token": get_or_create_csrf_token(), "auth_mode": get_auth_mode()})


@bp.put("/password")
@require_session
@require_csrf
def change_password():
    if not is_local_login_enabled():
        return error("AUTH409", "当前认证模式不支持修改本地管理员密码", status=409)
    payload = request.get_json(silent=True) or {}
    user = current_user()
    if not verify_password(payload.get("old_password", ""), user.password_hash):
        return error("AUTH422", "原密码错误", status=422)
    user.password_hash = hash_password(payload.get("new_password", ""))
    write_audit("change_password", "admin_user", str(user.id))
    db.session.commit()
    return success()
