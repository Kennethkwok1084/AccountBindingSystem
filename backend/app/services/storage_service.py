from __future__ import annotations

import hashlib
from datetime import date, datetime
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

CHARGE_EXPORT_COLUMNS = [
    "账号",
    "移动账户",
    "移动密码",
    "联通账户",
    "联通密码",
    "电信账户",
    "电信密码",
]

XLS_MAX_DATA_ROWS = 65535

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


def create_charge_execution_export_file(rows: list[dict]) -> tuple[str, str]:
    normalized_rows = []
    for row in rows:
        normalized_rows.append(
            {
                "账号": row.get("学号", row.get("账号", "")),
                "移动账户": row.get("移动账户", ""),
                "移动密码": row.get("移动密码", current_app.config["MOBILE_DEFAULT_PASSWORD"]),
                "联通账户": "",
                "联通密码": "",
                "电信账户": "",
                "电信密码": "",
            }
        )

    return create_tabular_export_file(normalized_rows, "移动", CHARGE_EXPORT_COLUMNS, suffix=".xls")


def create_tabular_export_file(
    rows: list[dict],
    prefix: str,
    columns: list[str] | None = None,
    suffix: str = ".xlsx",
) -> tuple[str, str]:
    storage_root = Path(current_app.config["STORAGE_ROOT"]) / "exports"
    storage_root.mkdir(parents=True, exist_ok=True)
    timestamp = localnow().strftime("%y%m%d%H%M%S")
    full_path = _next_export_path(storage_root, f"{prefix}{timestamp}", suffix)
    filename = full_path.name

    if columns:
        dataframe = pd.DataFrame(rows)
        for column in columns:
            if column not in dataframe.columns:
                dataframe[column] = ""
        dataframe = dataframe[columns]
    else:
        dataframe = pd.DataFrame(rows)
    _write_excel_file(dataframe, full_path)
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


def _write_excel_file(dataframe: pd.DataFrame, full_path: Path) -> None:
    if full_path.suffix.lower() == ".xls":
        _write_legacy_xls(dataframe, full_path)
        return
    dataframe.to_excel(full_path, index=False)


def _write_legacy_xls(dataframe: pd.DataFrame, full_path: Path) -> None:
    import xlwt

    if len(dataframe.index) > XLS_MAX_DATA_ROWS:
        raise ValueError(f".xls 导出最多支持 {XLS_MAX_DATA_ROWS} 行数据")
    if len(dataframe.columns) > 256:
        raise ValueError(".xls 导出最多支持 256 列")

    workbook = xlwt.Workbook(encoding="utf-8")
    sheet = workbook.add_sheet("Sheet1")
    header_style = xlwt.easyxf("font: bold on")
    text_style = xlwt.easyxf(num_format_str="@")

    for column_index, column_name in enumerate(dataframe.columns):
        sheet.write(0, column_index, column_name, header_style)

    for row_index, row in enumerate(dataframe.itertuples(index=False, name=None), start=1):
        for column_index, value in enumerate(row):
            sheet.write(row_index, column_index, _xls_cell_value(value), text_style)

    workbook.save(str(full_path))


def _xls_cell_value(value):
    if pd.isna(value):
        return ""
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
    return value
