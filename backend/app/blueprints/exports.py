from __future__ import annotations

from datetime import datetime, time
from pathlib import Path

from flask import Blueprint, request, send_file
from sqlalchemy import asc, desc

from ..extensions import db
from ..models import ExportJob
from ..responses import success
from ..security import require_session
from ..services.audit_service import write_audit
from ..services.export_service import export_download_path, mark_export_downloaded


bp = Blueprint("exports", __name__)


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


@bp.get("/exports")
@require_session
def exports():
    keyword = str(request.args.get("keyword") or "").strip()
    created_from = _parse_datetime_bound(request.args.get("created_from"))
    created_to = _parse_datetime_bound(request.args.get("created_to"), end_of_day=True)
    sort_by = request.args.get("sort_by", "id")
    sort_order = request.args.get("sort_order", "desc")
    page, page_size = _paging()

    query = ExportJob.query
    if keyword:
        query = query.filter(ExportJob.filename.ilike(f"%{keyword}%"))
    if created_from:
        query = query.filter(ExportJob.created_at >= created_from)
    if created_to:
        query = query.filter(ExportJob.created_at <= created_to)

    sortable_columns = {
        "id": ExportJob.id,
        "filename": ExportJob.filename,
        "row_count": ExportJob.row_count,
        "created_at": ExportJob.created_at,
        "downloaded_at": ExportJob.downloaded_at,
    }
    order_column = sortable_columns.get(sort_by, ExportJob.id)
    direction = desc if str(sort_order).lower() == "desc" else asc

    total = query.count()
    items = (
        query.order_by(direction(order_column), ExportJob.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return success(
        {
            "items": [
                {
                    "id": item.id,
                    "filename": item.filename,
                    "row_count": item.row_count,
                    "created_at": item.created_at.isoformat(),
                    "downloaded_at": item.downloaded_at.isoformat() if item.downloaded_at else None,
                }
                for item in items
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@bp.get("/exports/<int:export_id>/download")
@require_session
def download_export(export_id: int):
    export_job = ExportJob.query.get_or_404(export_id)
    write_audit("download_export", "export_job", str(export_id), {"filename": export_job.filename})
    db.session.commit()
    mark_export_downloaded(export_job)
    return send_file(Path(export_download_path(export_job)), as_attachment=True, download_name=export_job.filename)
