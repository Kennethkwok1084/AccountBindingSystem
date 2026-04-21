from __future__ import annotations

from pathlib import Path

from flask import Blueprint, send_file

from ..extensions import db
from ..models import ExportJob
from ..responses import success
from ..security import require_session
from ..services.audit_service import write_audit
from ..services.export_service import export_download_path, mark_export_downloaded


bp = Blueprint("exports", __name__)


@bp.get("/exports")
@require_session
def exports():
    items = ExportJob.query.order_by(ExportJob.id.desc()).all()
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
            ]
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
