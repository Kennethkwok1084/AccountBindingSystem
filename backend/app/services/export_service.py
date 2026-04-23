from __future__ import annotations

from datetime import datetime
from pathlib import Path

from flask import current_app

from ..auth import current_user
from ..extensions import db
from ..models import ExportJob
from ..services.audit_service import write_audit
from ..services.storage_service import create_export_file, create_tabular_export_file


def create_export(operation_batch_id: int | None, rows: list[dict]) -> ExportJob | None:
    if not rows:
        return None
    filename, stored_path = create_export_file(rows)
    return _create_export_job(operation_batch_id, filename, stored_path, len(rows))


def create_tabular_export(
    operation_batch_id: int | None,
    rows: list[dict],
    filename_prefix: str,
    columns: list[str] | None = None,
) -> ExportJob | None:
    if not rows:
        return None
    filename, stored_path = create_tabular_export_file(rows, filename_prefix, columns)
    return _create_export_job(operation_batch_id, filename, stored_path, len(rows))


def _create_export_job(operation_batch_id: int | None, filename: str, stored_path: str, row_count: int) -> ExportJob:
    user = current_user()
    export_job = ExportJob(
        operation_batch_id=operation_batch_id,
        filename=filename,
        stored_path=stored_path,
        row_count=row_count,
        status="ready",
        created_by=user.id,
    )
    db.session.add(export_job)
    db.session.flush()
    write_audit("create_export", "export_job", str(export_job.id), {"filename": filename, "row_count": row_count})
    return export_job


def export_download_path(export_job: ExportJob) -> Path:
    path = Path(export_job.stored_path)
    if path.is_absolute():
        return path
    return Path(current_app.config["STORAGE_ROOT"]) / path


def mark_export_downloaded(export_job: ExportJob) -> None:
    export_job.downloaded_at = datetime.utcnow()
    db.session.commit()
