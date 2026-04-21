from __future__ import annotations

from flask import Blueprint, request

from ..models import AuditLog
from ..responses import success
from ..security import require_session


bp = Blueprint("audit", __name__)


@bp.get("/audit-logs")
@require_session
def audit_logs():
    query = AuditLog.query.order_by(AuditLog.id.desc())
    if request.args.get("action"):
        query = query.filter(AuditLog.action == request.args["action"])
    if request.args.get("resource_type"):
        query = query.filter(AuditLog.resource_type == request.args["resource_type"])
    items = query.all()
    return success(
        {
            "items": [
                {
                    "id": item.id,
                    "action": item.action,
                    "resource_type": item.resource_type,
                    "resource_id": item.resource_id,
                    "detail_json": item.detail_json,
                    "created_at": item.created_at.isoformat(),
                }
                for item in items
            ]
        }
    )
