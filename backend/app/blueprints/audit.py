from __future__ import annotations

from datetime import datetime, time
import json

from flask import Blueprint, request
from sqlalchemy import asc, desc, or_

from ..models import AuditLog
from ..responses import error, success
from ..security import require_csrf, require_session
from ..services.export_service import create_tabular_export


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


def _build_audit_query(params=None):
    params = params or request.args
    query = AuditLog.query
    if params.get("action"):
        query = query.filter(AuditLog.action == params["action"])
    if params.get("resource_type"):
        query = query.filter(AuditLog.resource_type == params["resource_type"])

    resource_id = str(params.get("resource_id") or "").strip()
    if resource_id:
        query = query.filter(AuditLog.resource_id == resource_id)

    keyword = str(params.get("keyword") or "").strip()
    if keyword:
        query = query.filter(
            or_(
                AuditLog.action.ilike(f"%{keyword}%"),
                AuditLog.resource_type.ilike(f"%{keyword}%"),
                AuditLog.resource_id.ilike(f"%{keyword}%"),
            )
        )

    created_from = _parse_datetime_bound(params.get("created_from"))
    created_to = _parse_datetime_bound(params.get("created_to"), end_of_day=True)
    if created_from:
        query = query.filter(AuditLog.created_at >= created_from)
    if created_to:
        query = query.filter(AuditLog.created_at <= created_to)
    return query


@bp.get("/audit-logs")
@require_session
def audit_logs():
    query = _build_audit_query()
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


@bp.post("/audit-logs/export")
@require_session
@require_csrf
def export_audit_logs():
    payload = request.get_json(silent=True) or {}
    query = _build_audit_query(payload)
    sort_by = payload.get("sort_by", "created_at")
    sort_order = payload.get("sort_order", "desc")
    sortable_columns = {
        "id": AuditLog.id,
        "created_at": AuditLog.created_at,
        "action": AuditLog.action,
        "resource_type": AuditLog.resource_type,
        "resource_id": AuditLog.resource_id,
    }
    order_column = sortable_columns.get(sort_by, AuditLog.created_at)
    direction = desc if str(sort_order).lower() == "desc" else asc
    items = query.order_by(direction(order_column), AuditLog.id.desc()).all()
    if not items:
        return error("EXP422", "当前筛选条件下没有可导出的审计日志", status=422)

    export_job = create_tabular_export(
        None,
        [
            {
                "ID": item.id,
                "动作": item.action,
                "资源类型": item.resource_type,
                "资源ID": item.resource_id or "",
                "操作人ID": item.operator_id or "",
                "详情": json.dumps(item.detail_json or {}, ensure_ascii=False),
                "时间": item.created_at.isoformat(sep=" "),
            }
            for item in items
        ],
        filename_prefix="审计日志",
        columns=["ID", "动作", "资源类型", "资源ID", "操作人ID", "详情", "时间"],
    )
    return success(
        {
            "export_job": {
                "id": export_job.id,
                "filename": export_job.filename,
                "row_count": export_job.row_count,
            }
        },
        status=201,
    )
