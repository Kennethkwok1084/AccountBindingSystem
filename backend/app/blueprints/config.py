from __future__ import annotations

from flask import Blueprint, request

from ..responses import error, success
from ..security import require_csrf, require_session
from ..services.audit_service import write_audit
from ..services.config_service import serialize_configs, update_configs
from ..services.syslog_service import test_syslog_connectivity


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


@bp.post("/config/test-syslog")
@require_session
@require_csrf
def post_test_syslog():
    payload = request.get_json(silent=True) or {}
    try:
        result = test_syslog_connectivity(payload)
    except ValueError as exc:
        return error("CFG422", str(exc), status=422)
    except OSError as exc:
        return error("CFG502", f"Syslog 发送失败：{exc}", status=502)
    write_audit("test_syslog_connectivity", "system_config", detail=result)
    return success({"message": "Syslog 测试消息已发送", **result})
