from __future__ import annotations

from datetime import datetime
from pathlib import Path

from flask import current_app

from ..auth import current_user
from ..extensions import db
from ..models import ExportJob
from ..services.audit_service import write_audit
from ..services.storage_service import create_export_file


def create_export(operation_batch_id: int | None, rows: list[dict]) -> ExportJob | None:
    if not rows:
        return None
    filename, stored_path = create_export_file(rows)
    user = current_user()
    export_job = ExportJob(
        operation_batch_id=operation_batch_id,
        filename=filename,
        stored_path=stored_path,
        row_count=len(rows),
        status="ready",
        created_by=user.id,
    )
    db.session.add(export_job)
    db.session.flush()
    write_audit("create_export", "export_job", str(export_job.id), {"filename": filename, "row_count": len(rows)})
    return export_job


def export_download_path(export_job: ExportJob) -> Path:
    path = Path(export_job.stored_path)
    if path.is_absolute():
        return path
    return Path(current_app.config["STORAGE_ROOT"]) / path


def mark_export_downloaded(export_job: ExportJob) -> None:
    export_job.downloaded_at = datetime.utcnow()
    db.session.commit()

