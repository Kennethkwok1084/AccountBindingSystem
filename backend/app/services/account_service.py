from __future__ import annotations

from calendar import monthrange
from datetime import date
import re

from flask import current_app
from sqlalchemy import asc, desc
from sqlalchemy import select

from ..auth import current_user
from ..extensions import db
from ..models import AccountBatch, ImportJob, ImportJobError, MobileAccount
from ..services.audit_service import write_audit
from ..services.config_service import get_config_value
from ..services.date_service import normalize_date, utcnow
from ..services.excel_service import validate_excel
from ..services.serialization_service import to_jsonable
from ..services.storage_service import save_upload


ZERO_ACCOUNT_BATCH_CODE = "0元账户"
BATCH_CODE_MONTH_PATTERN = re.compile(r"^(?P<year>\d{4})(?P<month>0[1-9]|1[0-2])$")


def import_mobile_accounts(file):
    user = current_user()
    stored_path, checksum = save_upload(file, "account_pool")
    job = ImportJob(
        job_type="account_pool",
        original_filename=file.filename or "account_pool.xlsx",
        stored_path=stored_path,
        file_checksum=checksum,
        operator_id=user.id,
        status="validating",
    )
    db.session.add(job)
    db.session.flush()

    parse_result = validate_excel(stored_path, "account_pool")
    _persist_import_issues(job.id, parse_result.issues)
    job.sheet_name = parse_result.sheet_name
    job.mapping_json = {"columns": sorted(parse_result.available_columns)}
    if parse_result.has_fatal_errors:
        job.status = "failed"
        job.error_summary = _summarize_import_issues(parse_result.issues) or "账号池模板校验失败"
        job.failed_rows = len(parse_result.issues)
        job.finished_at = utcnow()
        current_app.logger.warning(
            "mobile account import failed validation: job_id=%s filename=%s summary=%s",
            job.id,
            job.original_filename,
            job.error_summary,
        )
        db.session.commit()
        return None, job

    job.total_rows = len(parse_result.rows) + len(parse_result.issues)
    job.status = "executing"

    success_rows = 0
    failed_rows = len(parse_result.issues)
    for row_no, row in enumerate(parse_result.rows, start=2):
        account = row["account"]
        batch_code = row["batch_code"]

        existing_account = db.session.execute(select(MobileAccount).filter_by(account=account)).scalar_one_or_none()
        if existing_account is not None:
            failed_rows += 1
            db.session.add(
                ImportJobError(
                    import_job_id=job.id,
                    row_no=row_no,
                    field_name="account",
                    error_code="duplicate_account",
                    error_message="移动账号已存在",
                    raw_data=to_jsonable(row),
                )
            )
            continue

        batch = db.session.execute(select(AccountBatch).filter_by(batch_code=batch_code)).scalar_one_or_none()
        if batch is None:
            batch = AccountBatch(
                batch_code=batch_code,
                batch_name=batch_code,
                batch_type=(row.get("batch_type") or "normal").strip(),
                priority=_derive_batch_priority(batch_code),
                expire_at=_derive_batch_expire_at(batch_code),
                warn_days=_default_warn_days(),
                status="active",
            )
            db.session.add(batch)
            db.session.flush()

        db.session.add(
            MobileAccount(
                account=account,
                password=current_app.config["MOBILE_DEFAULT_PASSWORD"],
                batch_id=batch.id,
                status="available",
            )
        )
        success_rows += 1

    job.success_rows = success_rows
    job.failed_rows = failed_rows
    job.status = "success" if failed_rows == 0 else "partial_success"
    job.finished_at = utcnow()
    write_audit("import_mobile_accounts", "import_job", str(job.id), {"success_rows": success_rows, "failed_rows": failed_rows})
    db.session.commit()
    return parse_result.rows, job


def query_mobile_accounts(
    status: str | None = None,
    batch_code: str | None = None,
    account_keyword: str | None = None,
    batch_type: str | None = None,
    sort_by: str = "id",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 50,
):
    query = MobileAccount.query.join(AccountBatch)
    if status:
        query = query.filter(MobileAccount.status == status)
    if batch_code:
        query = query.filter(AccountBatch.batch_code.ilike(f"%{batch_code.strip()}%"))
    if account_keyword:
        query = query.filter(MobileAccount.account.ilike(f"%{account_keyword.strip()}%"))
    if batch_type:
        query = query.filter(AccountBatch.batch_type == batch_type)

    sortable_columns = {
        "id": MobileAccount.id,
        "account": MobileAccount.account,
        "status": MobileAccount.status,
        "batch_code": AccountBatch.batch_code,
        "batch_type": AccountBatch.batch_type,
        "priority": AccountBatch.priority,
        "last_assigned_at": MobileAccount.last_assigned_at,
    }
    order_column = sortable_columns.get(sort_by, MobileAccount.id)
    direction = desc if str(sort_order).lower() == "desc" else asc

    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 50), 200))

    total = query.count()
    items = (
        query.order_by(direction(order_column), AccountBatch.id.desc(), MobileAccount.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def _persist_import_issues(job_id: int, issues) -> None:
    for issue in issues:
        db.session.add(
            ImportJobError(
                import_job_id=job_id,
                row_no=issue.row_no,
                field_name=issue.field_name,
                error_code=issue.error_code,
                error_message=issue.error_message,
                raw_data=to_jsonable(issue.raw_data),
            )
        )


def _summarize_import_issues(issues) -> str | None:
    prioritized_issues = [issue for issue in issues if issue.row_no == 0] or list(issues)
    if not prioritized_issues:
        return None
    return prioritized_issues[0].error_message


def _default_warn_days() -> int:
    return int(get_config_value("batch.warn_days_default", 1) or 1)


def _derive_batch_priority(batch_code: str) -> int:
    code = str(batch_code or "").strip()
    if code == ZERO_ACCOUNT_BATCH_CODE:
        return 0
    if BATCH_CODE_MONTH_PATTERN.fullmatch(code):
        return 999999 - int(code)
    return 100


def _derive_batch_expire_at(batch_code: str) -> date | None:
    code = str(batch_code or "").strip()
    if code == ZERO_ACCOUNT_BATCH_CODE:
        return normalize_date("2099-01-01")
    match = BATCH_CODE_MONTH_PATTERN.fullmatch(code)
    if not match:
        return None
    year = int(match.group("year"))
    month = int(match.group("month"))
    return date(year, month, monthrange(year, month)[1])
