from __future__ import annotations

from flask import Blueprint, current_app, request

from ..responses import error, success
from ..security import require_csrf, require_session
from ..services.charge_record_service import (
    DuplicateChargeRawImportError,
    export_charge_raw_records,
    import_charge_raw_records,
    list_charge_raw_imports,
    query_charge_raw_records,
)


bp = Blueprint("charge_records", __name__)


def _paging(default_page_size: int = 50):
    page = max(1, int(request.args.get("page", 1) or 1))
    page_size = max(1, min(int(request.args.get("page_size", default_page_size) or default_page_size), 200))
    return page, page_size


def _filters_from_args(args) -> dict:
    return {
        "source_month": args.get("source_month"),
        "import_job_id": args.get("import_job_id", type=int),
        "charge_time_from": args.get("charge_time_from"),
        "charge_time_to": args.get("charge_time_to"),
        "keyword": args.get("keyword"),
    }


@bp.post("/charge-record-imports")
@require_session
@require_csrf
def import_charge_records():
    file = request.files.get("file")
    if file is None:
        return error("CR400", "缺少上传文件", status=400)
    try:
        import_job = import_charge_raw_records(file)
    except DuplicateChargeRawImportError as exc:
        return error(
            "CR409",
            str(exc),
            status=409,
            details=[{"import_job_id": exc.import_job_id}],
        )
    except ValueError as exc:
        current_app.logger.warning("charge raw import rejected: %s", exc)
        return error("CR422", str(exc), status=422)
    return success(
        {
            "job_id": import_job.id,
            "status": import_job.status,
            "total_rows": import_job.total_rows,
            "success_rows": import_job.success_rows,
            "invalid_time_rows": (import_job.mapping_json or {}).get("invalid_time_rows", import_job.failed_rows),
            "source_months": (import_job.mapping_json or {}).get("source_months", []),
            "time_column": (import_job.mapping_json or {}).get("time_column"),
        },
        status=201,
    )


@bp.get("/charge-record-imports")
@require_session
def charge_record_imports():
    page, page_size = _paging()
    return success(list_charge_raw_imports(page=page, page_size=page_size))


@bp.get("/charge-records")
@require_session
def charge_records():
    page, page_size = _paging()
    payload = query_charge_raw_records(_filters_from_args(request.args), page=page, page_size=page_size)
    return success(payload)


@bp.post("/charge-records/export")
@require_session
@require_csrf
def charge_records_export():
    payload = request.get_json(silent=True) or {}
    try:
        export_job = export_charge_raw_records(payload)
    except ValueError as exc:
        return error("CR422", str(exc), status=422)
    return success(
        {
            "export_job": {
                "id": export_job.id,
                "filename": export_job.filename,
                "row_count": export_job.row_count,
            }
        },
        status=201,
    )
