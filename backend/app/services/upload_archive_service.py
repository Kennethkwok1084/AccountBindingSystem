from __future__ import annotations

import re
import zipfile
from collections import defaultdict
from pathlib import Path

from flask import current_app

from ..models import ImportJob


MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

CATEGORY_LABELS = {
    "account_pool": "账号池",
    "charge_list": "收费清单",
    "full_student_list": "完整名单",
}


def list_upload_archives() -> list[dict]:
    grouped: dict[str, dict] = {}
    jobs = ImportJob.query.order_by(ImportJob.created_at.desc(), ImportJob.id.desc()).all()
    for job in jobs:
        month = upload_job_month(job)
        archive = grouped.setdefault(
            month,
            {
                "month": month,
                "file_count": 0,
                "missing_count": 0,
                "total_size": 0,
                "categories": defaultdict(int),
            },
        )
        archive["file_count"] += 1
        archive["categories"][job.job_type] += 1
        path = resolve_upload_path(job.stored_path)
        if path and path.exists():
            archive["total_size"] += path.stat().st_size
        else:
            archive["missing_count"] += 1

    items = []
    for archive in grouped.values():
        categories = [
            {
                "job_type": job_type,
                "label": CATEGORY_LABELS.get(job_type, job_type),
                "count": count,
            }
            for job_type, count in sorted(archive["categories"].items())
        ]
        items.append(
            {
                "month": archive["month"],
                "file_count": archive["file_count"],
                "missing_count": archive["missing_count"],
                "total_size": archive["total_size"],
                "categories": categories,
            }
        )
    return sorted(items, key=lambda item: item["month"], reverse=True)


def create_upload_archive(month: str, target_path: Path) -> int:
    if not MONTH_PATTERN.fullmatch(month):
        raise ValueError("月份格式应为 YYYY-MM")

    jobs = [
        job
        for job in ImportJob.query.order_by(ImportJob.id.asc()).all()
        if upload_job_month(job) == month
    ]
    written = 0
    with zipfile.ZipFile(target_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for job in jobs:
            path = resolve_upload_path(job.stored_path)
            if not path or not path.exists() or not path.is_file():
                continue
            archive.write(path, _archive_name(month, job))
            written += 1
    return written


def upload_job_month(job: ImportJob) -> str:
    for part in Path(job.stored_path or "").parts:
        if MONTH_PATTERN.fullmatch(part):
            return part
    return job.created_at.strftime("%Y-%m")


def resolve_upload_path(stored_path: str | None) -> Path | None:
    if not stored_path:
        return None
    storage_root = Path(current_app.config["STORAGE_ROOT"]).resolve()
    uploads_root = (storage_root / "uploads").resolve()
    path = Path(stored_path)
    if not path.is_absolute():
        path = storage_root / path
    try:
        resolved = path.resolve()
        if not resolved.is_relative_to(uploads_root):
            return None
        return resolved
    except OSError:
        return None


def _archive_name(month: str, job: ImportJob) -> str:
    filename = Path(job.original_filename or Path(job.stored_path).name).name
    filename = filename.replace("/", "_").replace("\\", "_") or Path(job.stored_path).name
    category = job.job_type or "unknown"
    return f"{month}/{category}/{job.id}_{filename}"
