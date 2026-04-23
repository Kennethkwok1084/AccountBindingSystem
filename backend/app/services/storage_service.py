from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

import pandas as pd
from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from .date_service import localnow, utcnow


EXPORT_COLUMNS = [
    "学号",
    "移动账户",
    "移动密码",
    "联通账户",
    "联通密码",
    "电信账户",
    "电信密码",
]

ALLOWED_UPLOAD_SUFFIXES = {".xlsx", ".xls"}


def save_upload(file: FileStorage, category: str) -> tuple[str, str]:
    suffix = Path(file.filename or "upload.xlsx").suffix.lower()
    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        raise ValueError("仅支持上传 .xlsx 或 .xls 文件")

    storage_root = Path(current_app.config["STORAGE_ROOT"]) / "uploads" / category
    storage_root.mkdir(parents=True, exist_ok=True)
    filename = secure_filename(file.filename or f"{category}.xlsx")
    stored_name = f"{utcnow():%Y%m%d%H%M%S}_{uuid4().hex[:8]}_{filename}"
    full_path = storage_root / stored_name
    file.save(full_path)
    checksum = hashlib.sha256(full_path.read_bytes()).hexdigest()
    return str(full_path), checksum


def create_export_file(rows: list[dict]) -> tuple[str, str]:
    normalized_rows = []
    for row in rows:
        normalized_rows.append(
            {
                "学号": row.get("学号", ""),
                "移动账户": row.get("移动账户", ""),
                "移动密码": row.get("移动密码", current_app.config["MOBILE_DEFAULT_PASSWORD"]),
                "联通账户": "",
                "联通密码": "",
                "电信账户": "",
                "电信密码": "",
            }
        )

    return create_tabular_export_file(normalized_rows, "移动", EXPORT_COLUMNS)


def create_tabular_export_file(rows: list[dict], prefix: str, columns: list[str] | None = None) -> tuple[str, str]:
    storage_root = Path(current_app.config["STORAGE_ROOT"]) / "exports"
    storage_root.mkdir(parents=True, exist_ok=True)
    timestamp = localnow().strftime("%y%m%d%H%M%S")
    full_path = _next_export_path(storage_root, f"{prefix}{timestamp}", ".xlsx")
    filename = full_path.name

    if columns:
        dataframe = pd.DataFrame(rows)
        for column in columns:
            if column not in dataframe.columns:
                dataframe[column] = ""
        dataframe = dataframe[columns]
    else:
        dataframe = pd.DataFrame(rows)
    dataframe.to_excel(full_path, index=False)
    return filename, str(full_path)


def cleanup_temp_files(root: str, keep_days: int) -> int:
    base = Path(root)
    removed = 0
    threshold = utcnow().timestamp() - keep_days * 24 * 60 * 60
    for folder_name in ("tmp",):
        folder = base / folder_name
        if not folder.exists():
            continue
        for path in folder.rglob("*"):
            if path.is_file() and path.stat().st_mtime < threshold:
                path.unlink(missing_ok=True)
                removed += 1
    return removed


def _next_export_path(storage_root: Path, base_name: str, suffix: str) -> Path:
    candidate = storage_root / f"{base_name}{suffix}"
    if not candidate.exists():
        return candidate

    counter = 1
    while True:
        candidate = storage_root / f"{base_name}_{counter:02d}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1
