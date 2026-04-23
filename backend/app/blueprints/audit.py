from __future__ import annotations

from datetime import datetime, time

from flask import Blueprint, request
from sqlalchemy import asc, desc, or_

from ..models import AuditLog
from ..responses import success
from ..security import require_session


bp = Blueprint("audit", __name__)


def _paging(default_page_size: int = 50):
    page = max(1, int(request.args.get("page", 1) or 1))
    page_size = max(1, min(int(request.args.get("page_size", default_page_size) or default_page_size), 200))
    return page, page_size


def _parse_datetime_bound(value: str | None, end_of_day: bool = False):
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        if len(text) == 10:
            target_time = time.max if end_of_day else time.min
            return datetime.combine(datetime.fromisoformat(text).date(), target_time)
        return datetime.fromisoformat(text)
    except ValueError:
        return None


@bp.get("/audit-logs")
@require_session
def audit_logs():
    query = AuditLog.query
    if request.args.get("action"):
        query = query.filter(AuditLog.action == request.args["action"])
    if request.args.get("resource_type"):
        query = query.filter(AuditLog.resource_type == request.args["resource_type"])

    resource_id = str(request.args.get("resource_id") or "").strip()
    if resource_id:
        query = query.filter(AuditLog.resource_id == resource_id)

    keyword = str(request.args.get("keyword") or "").strip()
    if keyword:
        query = query.filter(
            or_(
                AuditLog.action.ilike(f"%{keyword}%"),
                AuditLog.resource_type.ilike(f"%{keyword}%"),
                AuditLog.resource_id.ilike(f"%{keyword}%"),
            )
        )

    created_from = _parse_datetime_bound(request.args.get("created_from"))
    created_to = _parse_datetime_bound(request.args.get("created_to"), end_of_day=True)
    if created_from:
        query = query.filter(AuditLog.created_at >= created_from)
    if created_to:
        query = query.filter(AuditLog.created_at <= created_to)

    sort_by = request.args.get("sort_by", "id")
    sort_order = request.args.get("sort_order", "desc")
    sortable_columns = {
        "id": AuditLog.id,
        "created_at": AuditLog.created_at,
        "action": AuditLog.action,
        "resource_type": AuditLog.resource_type,
        "resource_id": AuditLog.resource_id,
    }
    order_column = sortable_columns.get(sort_by, AuditLog.id)
    direction = desc if str(sort_order).lower() == "desc" else asc
    page, page_size = _paging()

    total = query.count()
    items = (
        query.order_by(direction(order_column), AuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return success(
        {
            "items": [
                {
                    "id": item.id,
                    "operator_id": item.operator_id,
                    "action": item.action,
                    "resource_type": item.resource_type,
                    "resource_id": item.resource_id,
                    "detail_json": item.detail_json,
                    "created_at": item.created_at.isoformat(),
                }
                for item in items
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )
