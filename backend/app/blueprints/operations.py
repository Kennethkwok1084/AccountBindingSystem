from __future__ import annotations

from flask import Blueprint, current_app, request

from ..auth import current_user
from ..models import ImportJobError, OperationBatch, OperationBatchDetail
from ..responses import error, success
from ..security import require_csrf, require_session
from ..services.operation_service import (
    execute_batch_rebind,
    execute_charge_batch,
    execute_full_students,
    get_import_job_detail,
    manual_rebind,
    preview_batch_rebind,
    preview_charge_batch,
    preview_full_students,
    start_execute_full_students_async,
)


bp = Blueprint("operations", __name__)


def _operation_error(exc: ValueError):
    message = str(exc)
    status = 400 if "X-Idempotency-Key" in message else 409
    return error("OP409" if status == 409 else "OP400", message, status=status)


@bp.post("/charge-batches/preview")
@require_session
@require_csrf
def charge_preview():
    file = request.files.get("file")
    if file is None:
        return error("IMP400", "缺少上传文件", status=400)
    try:
        operation_batch, import_job = preview_charge_batch(file)
    except ValueError as exc:
        return error("IMP422", str(exc), status=422)
    if operation_batch is None:
        issues = (
            ImportJobError.query.filter_by(import_job_id=import_job.id)
            .order_by(ImportJobError.row_no.asc(), ImportJobError.id.asc())
            .limit(200)
            .all()
        )
        return error(
            "IMP422",
            import_job.error_summary or "预览失败",
            status=422,
            details=[
                {
                    "row_no": issue.row_no,
                    "field_name": issue.field_name,
                    "error_code": issue.error_code,
                    "error_message": issue.error_message,
                }
                for issue in issues
            ],
        )
    issues = (
        ImportJobError.query.filter_by(import_job_id=import_job.id)
        .order_by(ImportJobError.row_no.asc(), ImportJobError.id.asc())
        .limit(200)
        .all()
    )
    details = OperationBatchDetail.query.filter_by(operation_batch_id=operation_batch.id).order_by(OperationBatchDetail.row_no.asc()).all()
    return success(
        {
            "operation_batch_id": operation_batch.id,
            "import_job_id": import_job.id,
            "last_processed_charge_time_before": operation_batch.last_processed_charge_time_before.isoformat(sep=" ") if operation_batch.last_processed_charge_time_before else None,
            "preview_rows": len(details),
            "import_error_count": len(issues),
            "to_allocate_count": sum(1 for detail in details if detail.action_plan == "allocate"),
            "to_renew_count": sum(1 for detail in details if detail.action_plan == "renew"),
            "to_rebind_count": sum(1 for detail in details if detail.action_plan == "rebind"),
            "fail_count": sum(1 for detail in details if detail.status == "failed"),
            "import_errors": [
                {
                    "row_no": issue.row_no,
                    "field_name": issue.field_name,
                    "error_code": issue.error_code,
                    "error_message": issue.error_message,
                }
                for issue in issues
            ],
            "details": [
                {
                    "row_no": detail.row_no,
                    "student_no": detail.student_no,
                    "name": detail.student_name,
                    "action_plan": detail.action_plan,
                    "new_mobile_account_id": detail.new_mobile_account_id,
                    "result_message": detail.result_message,
                }
                for detail in details
            ],
        },
        status=201,
    )


@bp.post("/charge-batches/<int:batch_id>/execute")
@require_session
@require_csrf
def charge_execute(batch_id: int):
    idempotency_key = request.headers.get("X-Idempotency-Key")
    try:
        operation_batch, export_job = execute_charge_batch(batch_id, idempotency_key)
    except LookupError as exc:
        return error("OP404", str(exc), status=404)
    except ValueError as exc:
        return _operation_error(exc)
    return success(
        {
            "operation_batch_id": operation_batch.id,
            "status": operation_batch.status,
            "success_count": operation_batch.success_rows,
            "fail_count": operation_batch.failed_rows,
            "export_job": (
                {
                    "id": export_job.id,
                    "filename": export_job.filename,
                    "row_count": export_job.row_count,
                }
                if export_job
                else None
            ),
            "last_processed_charge_time_after": operation_batch.last_processed_charge_time_after.isoformat(sep=" ") if operation_batch.last_processed_charge_time_after else None,
        }
    )


@bp.get("/charge-batches")
@require_session
def charge_batches():
    items = OperationBatch.query.filter_by(batch_type="charge_batch").order_by(OperationBatch.id.desc()).all()
    return success(
        {
            "items": [
                {
                    "id": item.id,
                    "status": item.status,
                    "success_rows": item.success_rows,
                    "failed_rows": item.failed_rows,
                    "executed_at": item.executed_at.isoformat() if item.executed_at else None,
                }
                for item in items
            ],
            "total": len(items),
        }
    )


@bp.get("/operation-batches/<int:batch_id>")
@require_session
def operation_batch_summary(batch_id: int):
    batch = OperationBatch.query.get_or_404(batch_id)
    processed_rows = batch.success_rows + batch.failed_rows
    progress_percent = 100.0 if batch.total_rows == 0 else round(processed_rows * 100 / batch.total_rows, 2)
    return success(
        {
            "id": batch.id,
            "batch_type": batch.batch_type,
            "status": batch.status,
            "total_rows": batch.total_rows,
            "processed_rows": processed_rows,
            "progress_percent": progress_percent,
            "success_rows": batch.success_rows,
            "failed_rows": batch.failed_rows,
            "last_processed_charge_time_before": batch.last_processed_charge_time_before.isoformat(sep=" ") if batch.last_processed_charge_time_before else None,
            "last_processed_charge_time_after": batch.last_processed_charge_time_after.isoformat(sep=" ") if batch.last_processed_charge_time_after else None,
            "executed_at": batch.executed_at.isoformat() if batch.executed_at else None,
        }
    )


@bp.get("/operation-batches/<int:batch_id>/details")
@require_session
def operation_batch_details(batch_id: int):
    result_status = request.args.get("result_status")
    query = OperationBatchDetail.query.filter_by(operation_batch_id=batch_id)
    if result_status:
        query = query.filter(OperationBatchDetail.status == result_status)
    rows = query.order_by(OperationBatchDetail.row_no.asc()).all()
    return success(
        {
            "items": [
                {
                    "id": row.id,
                    "row_no": row.row_no,
                    "student_no": row.student_no,
                    "student_name": row.student_name,
                    "action_plan": row.action_plan,
                    "status": row.status,
                    "old_mobile_account_id": row.old_mobile_account_id,
                    "new_mobile_account_id": row.new_mobile_account_id,
                    "result_message": row.result_message,
                }
                for row in rows
            ],
            "total": len(rows),
        }
    )


@bp.get("/imports/<int:job_id>")
@require_session
def import_job_detail(job_id: int):
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 50))
    try:
        payload = get_import_job_detail(job_id, page=page, page_size=page_size)
    except LookupError as exc:
        return error("IMP404", str(exc), status=404)
    return success(payload)


@bp.post("/full-students/import/preview")
@require_session
@require_csrf
def full_students_preview():
    file = request.files.get("file")
    if file is None:
        return error("IMP400", "缺少上传文件", status=400)
    try:
        preview, import_job = preview_full_students(file)
    except ValueError as exc:
        return error("IMP422", str(exc), status=422)
    if preview is None:
        return error("IMP422", import_job.error_summary or "预览失败", status=422)
    return success({"job_id": import_job.id, **preview}, status=201)


@bp.post("/full-students/import/<int:job_id>/execute")
@require_session
@require_csrf
def full_students_execute(job_id: int):
    idempotency_key = request.headers.get("X-Idempotency-Key")
    try:
        result = execute_full_students(job_id, idempotency_key)
    except LookupError as exc:
        return error("OP404", str(exc), status=404)
    except ValueError as exc:
        return _operation_error(exc)
    return success(result)


@bp.post("/full-students/import/<int:job_id>/execute-async")
@require_session
@require_csrf
def full_students_execute_async(job_id: int):
    idempotency_key = request.headers.get("X-Idempotency-Key")
    user = current_user()
    if user is None:
        return error("AUTH401", "登录状态已失效，请重新登录", status=401)
    try:
        operation_batch, started = start_execute_full_students_async(
            job_id,
            idempotency_key,
            user.id,
            current_app._get_current_object(),
        )
    except LookupError as exc:
        return error("OP404", str(exc), status=404)
    except ValueError as exc:
        return _operation_error(exc)
    return success(
        {
            "operation_batch_id": operation_batch.id,
            "job_id": job_id,
            "status": operation_batch.status,
            "started": started,
            "total_rows": operation_batch.total_rows,
            "success_rows": operation_batch.success_rows,
            "failed_rows": operation_batch.failed_rows,
        },
        status=202,
    )


@bp.post("/bindings/manual-rebind")
@require_session
@require_csrf
def binding_manual_rebind():
    payload = request.get_json(silent=True) or {}
    idempotency_key = request.headers.get("X-Idempotency-Key")
    try:
        operation_batch, student, old_account, new_account, export_job = manual_rebind(
            payload.get("student_no", ""),
            payload.get("old_account_action", "release"),
            payload.get("remark"),
            idempotency_key,
        )
    except (TypeError, ValueError) as exc:
        if isinstance(exc, ValueError):
            return _operation_error(exc)
        return error("OP400", str(exc), status=400)
    except LookupError as exc:
        return error("OP404", str(exc), status=404)
    return success(
        {
            "operation_batch_id": operation_batch.id,
            "student_no": student.student_no,
            "old_account": old_account.account if old_account else None,
            "new_account": new_account.account,
            "export_job": {"id": export_job.id, "filename": export_job.filename, "row_count": export_job.row_count},
        }
    )


@bp.post("/batch-rebinds/preview")
@require_session
@require_csrf
def batch_rebind_preview():
    payload = request.get_json(silent=True) or {}
    try:
        batch, rows = preview_batch_rebind(int(payload.get("batch_id")))
    except (TypeError, ValueError):
        return error("BAT400", "batch_id 非法", status=400)
    except LookupError as exc:
        return error("BAT404", str(exc), status=404)
    return success({"batch_id": batch.id, "batch_code": batch.batch_code, "items": rows})


@bp.post("/batch-rebinds/<int:batch_id>/execute")
@require_session
@require_csrf
def batch_rebind_execute(batch_id: int):
    idempotency_key = request.headers.get("X-Idempotency-Key")
    try:
        batch, export_job = execute_batch_rebind(batch_id, idempotency_key)
    except LookupError as exc:
        return error("BAT404", str(exc), status=404)
    except ValueError as exc:
        return _operation_error(exc)
    return success(
        {
            "operation_batch_id": batch.id,
            "status": batch.status,
            "success_rows": batch.success_rows,
            "failed_rows": batch.failed_rows,
            "export_job": (
                {"id": export_job.id, "filename": export_job.filename, "row_count": export_job.row_count}
                if export_job
                else None
            ),
        }
    )
