from __future__ import annotations

from flask import Blueprint, request

from ..responses import success
from ..security import require_csrf, require_session
from ..services.audit_service import write_audit
from ..services.config_service import serialize_configs, update_configs


bp = Blueprint("config", __name__)


@bp.get("/config")
@require_session
def get_configs():
    items = serialize_configs()
    return success(items)


@bp.put("/config")
@require_session
@require_csrf
def put_configs():
    payload = request.get_json(silent=True) or {}
    update_configs(payload)
    write_audit("update_config", "system_config", detail={"keys": list(payload.keys())})
    return success(payload)
