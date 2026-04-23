from __future__ import annotations

from datetime import datetime
import re
from urllib.parse import quote

from flask import Blueprint, request
from sqlalchemy import asc, desc, func, or_

from ..extensions import db
from ..models import AccountBatch, AlertRecord, Student
from ..responses import success
from ..security import require_csrf, require_session


bp = Blueprint("alerts", __name__)


_STUDENT_NO_PATTERN = re.compile(r"学号\s*([^\s]+)")


def _bool_arg(value: str | None):
    if value is None or value == "":
        return None
    return str(value).lower() == "true"


def _paging_args(default_page_size: int = 50):
    page = max(1, int(request.args.get("page", 1) or 1))
    page_size = max(1, min(int(request.args.get("page_size", default_page_size) or default_page_size), 200))
    return page, page_size


def _extract_conflict_reason(content: str) -> str:
    if not content:
        return "未分类冲突"
    if "学号" in content:
        matched = _STUDENT_NO_PATTERN.search(content)
        if matched:
            prefix = matched.group(0)
            reason = content.replace(prefix, "", 1).strip()
            return reason or "未分类冲突"
    return content.strip() or "未分类冲突"


def _extract_student_no(content: str) -> str | None:
    if not content:
        return None
    matched = _STUDENT_NO_PATTERN.search(content)
    if not matched:
        return None
    return matched.group(1)


def _alert_action(alert: AlertRecord, batch_code: str | None, student_no: str | None):
    if alert.type == "batch_expire" and alert.related_batch_id:
        return {
            "action_hint": "batch_rebind",
            "action_label": "去批量换号",
            "action_target": f"/operations/batch-rebind?batch_id={alert.related_batch_id}",
            "related_batch_code": batch_code,
            "related_student_no": student_no,
        }
    if alert.type == "binding_conflict":
        if student_no:
            return {
                "action_hint": "manual_rebind",
                "action_label": "去手动换绑",
                "action_target": f"/operations/manual-rebind?student_no={quote(student_no)}",
                "related_batch_code": batch_code,
                "related_student_no": student_no,
            }
        return {
            "action_hint": "manual_rebind",
            "action_label": "去手动换绑",
            "action_target": "/operations/manual-rebind",
            "related_batch_code": batch_code,
            "related_student_no": student_no,
        }
    return {
        "action_hint": None,
        "action_label": None,
        "action_target": None,
        "related_batch_code": batch_code,
        "related_student_no": student_no,
    }


@bp.get("/alerts")
@require_session
def alerts():
    query = (
        db.session.query(AlertRecord, AccountBatch.batch_code, Student.student_no)
        .outerjoin(AccountBatch, AccountBatch.id == AlertRecord.related_batch_id)
        .outerjoin(Student, Student.id == AlertRecord.related_student_id)
    )

    if request.args.get("type"):
        query = query.filter(AlertRecord.type == request.args.get("type"))

    if request.args.get("is_resolved") is not None:
        query = query.filter(AlertRecord.is_resolved == (request.args.get("is_resolved") == "true"))

    if request.args.get("level"):
        query = query.filter(AlertRecord.level == request.args.get("level"))

    keyword = str(request.args.get("keyword") or "").strip()
    if keyword:
        query = query.filter(
            or_(
                AlertRecord.title.ilike(f"%{keyword}%"),
                AlertRecord.content.ilike(f"%{keyword}%"),
            )
        )

    sort_by = request.args.get("sort_by", "id")
    sort_order = request.args.get("sort_order", "desc")
    sortable_columns = {
        "id": AlertRecord.id,
        "created_at": AlertRecord.created_at,
        "type": AlertRecord.type,
        "level": AlertRecord.level,
        "status": AlertRecord.status,
        "is_resolved": AlertRecord.is_resolved,
    }
    order_column = sortable_columns.get(sort_by, AlertRecord.id)
    direction = desc if str(sort_order).lower() == "desc" else asc
    page, page_size = _paging_args()

    total = query.with_entities(func.count(AlertRecord.id)).scalar() or 0
    items = (
        query.order_by(direction(order_column), AlertRecord.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    payload_items = []
    for item, batch_code, student_no in items:
        derived_student_no = student_no or _extract_student_no(item.content)
        action = _alert_action(item, batch_code, derived_student_no)
        payload_items.append(
            {
                "id": item.id,
                "type": item.type,
                "level": item.level,
                "title": item.title,
                "content": item.content,
                "status": item.status,
                "is_resolved": item.is_resolved,
                "resolution_note": item.resolution_note,
                "related_batch_id": item.related_batch_id,
                "related_student_id": item.related_student_id,
                "conflict_reason": _extract_conflict_reason(item.content) if item.type == "binding_conflict" else None,
                "created_at": item.created_at.isoformat(),
                **action,
            }
        )

    return success(
        {
            "items": payload_items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@bp.get("/alerts/conflict-groups")
@require_session
def conflict_groups():
    include_resolved = _bool_arg(request.args.get("include_resolved"))
    keyword = str(request.args.get("keyword") or "").strip()
    page, page_size = _paging_args(default_page_size=20)

    query = (
        db.session.query(AlertRecord, Student.student_no)
        .outerjoin(Student, Student.id == AlertRecord.related_student_id)
        .filter(AlertRecord.type == "binding_conflict")
    )
    if include_resolved is not True:
        query = query.filter(AlertRecord.is_resolved.is_(False))
    if keyword:
        query = query.filter(AlertRecord.content.ilike(f"%{keyword}%"))

    rows = query.order_by(AlertRecord.id.desc()).all()
    grouped = {}
    for alert, joined_student_no in rows:
        reason = _extract_conflict_reason(alert.content)
        current = grouped.setdefault(
            reason,
            {
                "conflict_reason": reason,
                "count": 0,
                "student_nos": set(),
                "alert_ids": [],
            },
        )
        current["count"] += 1
        current["alert_ids"].append(alert.id)
        student_no = joined_student_no or _extract_student_no(alert.content)
        if student_no:
            current["student_nos"].add(student_no)

    groups = []
    for group in grouped.values():
        student_nos = sorted(group["student_nos"])
        groups.append(
            {
                "conflict_reason": group["conflict_reason"],
                "count": group["count"],
                "student_nos": student_nos,
                "joined_student_nos": "\n".join(student_nos),
                "alert_ids": sorted(group["alert_ids"], reverse=True),
            }
        )
    groups.sort(key=lambda item: (-item["count"], item["conflict_reason"]))

    total = len(groups)
    paged_groups = groups[(page - 1) * page_size : (page - 1) * page_size + page_size]
    return success({"items": paged_groups, "total": total, "page": page, "page_size": page_size})


@bp.patch("/alerts/<int:alert_id>/resolve")
@require_session
@require_csrf
def resolve_alert(alert_id: int):
    alert = AlertRecord.query.get_or_404(alert_id)
    payload = request.get_json(silent=True) or {}
    alert.is_resolved = True
    alert.status = "resolved"
    alert.resolution_note = payload.get("resolution_note")
    alert.resolved_at = datetime.utcnow()
    db.session.commit()
    return success({"id": alert.id, "is_resolved": alert.is_resolved})

