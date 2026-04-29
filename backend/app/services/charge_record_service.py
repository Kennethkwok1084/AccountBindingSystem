from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path
import threading

import pandas as pd
from flask import current_app
from sqlalchemy import String, cast, select

from ..auth import current_user
from ..extensions import db
from ..models import ChargeRawRecord, ImportJob
from .audit_service import record_operation_event, write_audit
from .date_service import utcnow
from .export_service import create_tabular_export
from .serialization_service import to_jsonable
from .storage_service import save_upload


CHARGE_RAW_JOB_TYPE = "charge_records_raw"
TIME_COLUMN_ALIASES = ("收费时间", "状态时间", "charge_time")
EXPORT_META_COLUMNS = ["导入任务ID", "源文件", "行号", "工作表", "来源月份", "解析收费时间", "原始时间值"]
MAX_EXPORT_ROWS = 100000


@dataclass(frozen=True)
class DuplicateChargeRawImportError(Exception):
    import_job_id: int

    def __str__(self) -> str:
        return "该文件已导入，禁止重复入库"


def import_charge_raw_records(file) -> ImportJob:
    user = current_user()
    stored_path, checksum = save_upload(file, "charge_records_raw")
    try:
        return import_charge_raw_records_from_path(
            stored_path=stored_path,
            original_filename=file.filename or "charge-records.xlsx",
            checksum=checksum,
            operator_id=user.id,
        )
    except DuplicateChargeRawImportError:
        Path(stored_path).unlink(missing_ok=True)
        raise


def start_charge_raw_archive_task(
    *,
    stored_path: str,
    original_filename: str,
    checksum: str,
    operator_id: int,
    app=None,
) -> None:
    """Archive an uploaded charge list in the background.

    Tests run this inline so assertions can observe deterministic results.
    """
    app = app or current_app._get_current_object()
    if app.config.get("TESTING"):
        try:
            import_charge_raw_records_from_path(
                stored_path=stored_path,
                original_filename=original_filename,
                checksum=checksum,
                operator_id=operator_id,
            )
        except DuplicateChargeRawImportError:
            db.session.rollback()
            app.logger.info("charge raw archive skipped duplicate file: checksum=%s", checksum)
        except Exception:  # noqa: BLE001
            db.session.rollback()
            app.logger.exception("charge raw archive failed: stored_path=%s", stored_path)
        return

    worker = threading.Thread(
        target=_run_charge_raw_archive_task,
        args=(app, stored_path, original_filename, checksum, operator_id),
        daemon=True,
        name=f"charge-raw-archive-{checksum[:8]}",
    )
    worker.start()


def import_charge_raw_records_from_path(
    *,
    stored_path: str,
    original_filename: str,
    checksum: str,
    operator_id: int,
) -> ImportJob:
    duplicate = _find_duplicate_import(checksum)
    if duplicate is not None:
        raise DuplicateChargeRawImportError(duplicate.id)

    import_job = ImportJob(
        job_type=CHARGE_RAW_JOB_TYPE,
        original_filename=original_filename or "charge-records.xlsx",
        stored_path=stored_path,
        file_checksum=checksum,
        operator_id=operator_id,
        status="validating",
    )
    db.session.add(import_job)
    db.session.flush()

    try:
        parsed = _read_raw_charge_excel(stored_path)
    except ValueError as exc:
        import_job.status = "failed"
        import_job.error_summary = str(exc)
        import_job.finished_at = utcnow()
        db.session.commit()
        raise

    rows = []
    invalid_time_rows = 0
    source_months: set[str] = set()
    for raw_row in parsed["rows"]:
        parsed_charge_time = raw_row["parsed_charge_time"]
        source_month = parsed_charge_time.strftime("%Y-%m") if parsed_charge_time else None
        if source_month:
            source_months.add(source_month)
        else:
            invalid_time_rows += 1
        record = ChargeRawRecord(
            import_job_id=import_job.id,
            row_no=raw_row["row_no"],
            sheet_name=parsed["sheet_name"],
            source_month=source_month,
            parsed_charge_time=parsed_charge_time,
            raw_time_text=raw_row["raw_time_text"],
            raw_data=raw_row["raw_data"],
            row_hash=_row_hash(raw_row["raw_data"]),
        )
        db.session.add(record)
        rows.append(record)

    import_job.sheet_name = parsed["sheet_name"]
    import_job.mapping_json = {
        "columns": parsed["columns"],
        "time_column": parsed["time_column"],
        "source_months": sorted(source_months),
        "invalid_time_rows": invalid_time_rows,
    }
    import_job.total_rows = len(rows)
    import_job.success_rows = len(rows)
    import_job.failed_rows = invalid_time_rows
    import_job.status = "partial_success" if invalid_time_rows else "success"
    import_job.finished_at = utcnow()
    write_audit(
        "import_charge_raw_records",
        "import_job",
        str(import_job.id),
        {
            "filename": import_job.original_filename,
            "total_rows": import_job.total_rows,
            "invalid_time_rows": invalid_time_rows,
        },
    )
    record_operation_event(
        "charge_raw_import",
        "import",
        import_job_id=import_job.id,
        operator_id=operator_id,
        decision={
            "total_rows": import_job.total_rows,
            "source_months": sorted(source_months),
            "invalid_time_rows": invalid_time_rows,
        },
    )
    db.session.commit()
    return import_job


def _run_charge_raw_archive_task(app, stored_path: str, original_filename: str, checksum: str, operator_id: int) -> None:
    with app.app_context():
        try:
            import_charge_raw_records_from_path(
                stored_path=stored_path,
                original_filename=original_filename,
                checksum=checksum,
                operator_id=operator_id,
            )
        except DuplicateChargeRawImportError:
            db.session.rollback()
            app.logger.info("charge raw archive skipped duplicate file: checksum=%s", checksum)
        except Exception:  # noqa: BLE001
            db.session.rollback()
            app.logger.exception("charge raw archive failed: stored_path=%s", stored_path)
        finally:
            db.session.remove()


def list_charge_raw_imports(page: int = 1, page_size: int = 50) -> dict:
    query = ImportJob.query.filter_by(job_type=CHARGE_RAW_JOB_TYPE)
    total = query.count()
    items = query.order_by(ImportJob.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [_serialize_import_job(item) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def query_charge_raw_records(filters: dict, page: int = 1, page_size: int = 50, export_all: bool = False) -> dict:
    query = _charge_record_query(filters)
    total = query.count()
    query = _order_records(query)
    if not export_all:
        query = query.offset((page - 1) * page_size).limit(page_size)
    items = query.all()
    return {
        "items": [_serialize_record(record, import_job) for record, import_job in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def export_charge_raw_records(filters: dict):
    result = query_charge_raw_records(filters, export_all=True)
    items = result["items"]
    if not items:
        raise ValueError("当前筛选条件下没有可导出的收费归档数据")
    if len(items) > MAX_EXPORT_ROWS:
        raise ValueError(f"收费归档导出最多支持 {MAX_EXPORT_ROWS} 行")

    raw_columns: list[str] = []
    seen_columns = set()
    for item in items:
        for column in item["raw_data"].keys():
            if column not in seen_columns:
                seen_columns.add(column)
                raw_columns.append(column)

    rows = []
    for item in items:
        raw_data = item["raw_data"]
        row = {
            "导入任务ID": item["import_job_id"],
            "源文件": item["original_filename"],
            "行号": item["row_no"],
            "工作表": item["sheet_name"] or "",
            "来源月份": item["source_month"] or "",
            "解析收费时间": item["parsed_charge_time"] or "",
            "原始时间值": item["raw_time_text"] or "",
        }
        for column in raw_columns:
            row[column] = raw_data.get(column, "")
        rows.append(row)

    export_job = create_tabular_export(None, rows, "收费归档合并", columns=EXPORT_META_COLUMNS + raw_columns)
    write_audit(
        "export_charge_raw_records",
        "export_job",
        str(export_job.id),
        {"row_count": export_job.row_count, "filters": filters},
    )
    db.session.commit()
    return export_job


def _find_duplicate_import(checksum: str) -> ImportJob | None:
    return db.session.execute(
        select(ImportJob)
        .filter(
            ImportJob.job_type == CHARGE_RAW_JOB_TYPE,
            ImportJob.file_checksum == checksum,
            ImportJob.status.in_(("success", "partial_success")),
        )
        .order_by(ImportJob.id.desc())
    ).scalars().first()


def _read_raw_charge_excel(path: str) -> dict:
    try:
        workbook = pd.ExcelFile(path)
    except ValueError as exc:
        raise ValueError(f"收费归档 Excel 无法读取：{exc}") from exc
    if not workbook.sheet_names:
        raise ValueError("收费归档 Excel 缺少工作表")

    sheet_name = workbook.sheet_names[0]
    dataframe = pd.read_excel(path, sheet_name=sheet_name, dtype=object)
    dataframe = dataframe.where(pd.notnull(dataframe), None)
    dataframe.columns = [str(column).strip() for column in dataframe.columns]
    columns = list(dataframe.columns)
    time_column = _resolve_time_column(columns)
    if time_column is None:
        raise ValueError("收费归档 Excel 缺少收费时间列：收费时间、状态时间 或 charge_time")

    rows = []
    for row_no, raw_row in enumerate(dataframe.to_dict(orient="records"), start=2):
        raw_data = to_jsonable(raw_row)
        raw_time_value = raw_row.get(time_column)
        parsed_charge_time = _parse_charge_time(raw_time_value)
        rows.append(
            {
                "row_no": row_no,
                "raw_data": raw_data,
                "raw_time_text": _raw_time_text(raw_time_value),
                "parsed_charge_time": parsed_charge_time,
            }
        )
    return {"sheet_name": sheet_name, "columns": columns, "time_column": time_column, "rows": rows}


def _resolve_time_column(columns: list[str]) -> str | None:
    normalized = {column.strip().lower(): column for column in columns}
    for alias in TIME_COLUMN_ALIASES:
        column = normalized.get(alias.lower())
        if column:
            return column
    return None


def _parse_charge_time(value) -> datetime | None:
    if value is None or value == "":
        return None
    try:
        parsed = pd.to_datetime(value, errors="coerce")
    except Exception:  # noqa: BLE001
        return None
    if pd.isna(parsed):
        return None
    if isinstance(parsed, pd.Timestamp):
        return parsed.to_pydatetime().replace(tzinfo=None)
    if isinstance(parsed, datetime):
        return parsed.replace(tzinfo=None)
    return None


def _raw_time_text(value) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except TypeError:
            return str(value)
    return str(value)


def _row_hash(raw_data: dict) -> str:
    payload = json.dumps(raw_data, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _charge_record_query(filters: dict):
    query = db.session.query(ChargeRawRecord, ImportJob).join(ImportJob, ImportJob.id == ChargeRawRecord.import_job_id)
    source_month = str(filters.get("source_month") or "").strip()
    if source_month:
        query = query.filter(ChargeRawRecord.source_month == source_month)

    import_job_id = filters.get("import_job_id")
    if import_job_id:
        query = query.filter(ChargeRawRecord.import_job_id == int(import_job_id))

    charge_time_from = _parse_datetime_bound(filters.get("charge_time_from"))
    if charge_time_from:
        query = query.filter(ChargeRawRecord.parsed_charge_time >= charge_time_from)

    charge_time_to = _parse_datetime_bound(filters.get("charge_time_to"), end_of_day=True)
    if charge_time_to:
        query = query.filter(ChargeRawRecord.parsed_charge_time <= charge_time_to)

    keyword = str(filters.get("keyword") or "").strip()
    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter(
            cast(ChargeRawRecord.raw_data, String).ilike(pattern)
            | ImportJob.original_filename.ilike(pattern)
            | ChargeRawRecord.raw_time_text.ilike(pattern)
        )
    return query


def _order_records(query):
    return query.order_by(
        ChargeRawRecord.parsed_charge_time.is_(None).asc(),
        ChargeRawRecord.parsed_charge_time.asc(),
        ChargeRawRecord.import_job_id.asc(),
        ChargeRawRecord.row_no.asc(),
    )


def _parse_datetime_bound(value: str | None, end_of_day: bool = False) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        if len(text) == 10:
            target_time = time.max if end_of_day else time.min
            return datetime.combine(datetime.fromisoformat(text).date(), target_time)
        return datetime.fromisoformat(text).replace(tzinfo=None)
    except ValueError:
        return None


def _serialize_import_job(import_job: ImportJob) -> dict:
    mapping = import_job.mapping_json or {}
    return {
        "id": import_job.id,
        "job_type": import_job.job_type,
        "original_filename": import_job.original_filename,
        "status": import_job.status,
        "sheet_name": import_job.sheet_name,
        "time_column": mapping.get("time_column"),
        "source_months": mapping.get("source_months", []),
        "total_rows": import_job.total_rows,
        "success_rows": import_job.success_rows,
        "invalid_time_rows": mapping.get("invalid_time_rows", import_job.failed_rows),
        "created_at": import_job.created_at.isoformat() if import_job.created_at else None,
        "finished_at": import_job.finished_at.isoformat() if import_job.finished_at else None,
    }


def _serialize_record(record: ChargeRawRecord, import_job: ImportJob) -> dict:
    return {
        "id": record.id,
        "import_job_id": record.import_job_id,
        "original_filename": import_job.original_filename,
        "row_no": record.row_no,
        "sheet_name": record.sheet_name,
        "source_month": record.source_month,
        "parsed_charge_time": record.parsed_charge_time.isoformat(sep=" ") if record.parsed_charge_time else None,
        "raw_time_text": record.raw_time_text,
        "raw_data": record.raw_data,
        "row_hash": record.row_hash,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }
