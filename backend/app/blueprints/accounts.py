from __future__ import annotations

from io import BytesIO

from flask import Blueprint, current_app, request, send_file
import pandas as pd

from ..extensions import db
from ..models import AccountBatch, ImportJobError, MobileAccount
from ..responses import error, success
from ..security import require_csrf, require_session
from ..services.account_service import import_mobile_accounts, query_mobile_accounts
from ..services.audit_service import write_audit
from ..services.date_service import normalize_date


bp = Blueprint("accounts", __name__)


@bp.post("/mobile-accounts/import")
@require_session
@require_csrf
def import_accounts():
    file = request.files.get("file")
    if file is None:
        return error("IMP400", "缺少上传文件", status=400)
    try:
        _, job = import_mobile_accounts(file)
    except ValueError as exc:
        current_app.logger.warning("mobile account import rejected before validation: %s", exc)
        return error("IMP422", str(exc), status=422)
    if job.status == "failed":
        return error(
            "IMP422",
            job.error_summary or "导入失败",
            status=422,
            details=_serialize_import_errors(job.id),
        )
    return success(
        {
            "job_id": job.id,
            "status": job.status,
            "success_rows": job.success_rows,
            "failed_rows": job.failed_rows,
        },
        status=201,
    )


@bp.get("/mobile-accounts/template")
@require_session
def download_mobile_account_template():
    buffer = BytesIO()
    pd.DataFrame([{"account": "yd0001", "batch_code": "202604"}]).to_excel(buffer, index=False)
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name="account-pool-template.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.get("/mobile-accounts")
@require_session
def mobile_accounts():
    status_filter = request.args.get("status")
    batch_code = request.args.get("batch_code")
    items = query_mobile_accounts(status_filter, batch_code)
    return success(
        {
            "items": [
                {
                    "id": item.id,
                    "account": item.account,
                    "status": item.status,
                    "disabled_reason": item.disabled_reason,
                    "last_assigned_at": item.last_assigned_at.isoformat() if item.last_assigned_at else None,
                    "batch_code": item.batch.batch_code,
                    "batch_type": item.batch.batch_type,
                }
                for item in items
            ],
            "total": len(items),
        }
    )


@bp.get("/mobile-accounts/<int:account_id>")
@require_session
def mobile_account_detail(account_id: int):
    account = db.session.get(MobileAccount, account_id)
    if account is None:
        return error("ACC404", "账号不存在", status=404)
    return success(
        {
            "id": account.id,
            "account": account.account,
            "status": account.status,
            "disabled_reason": account.disabled_reason,
            "batch": {
                "id": account.batch.id,
                "batch_code": account.batch.batch_code,
                "batch_name": account.batch.batch_name,
                "batch_type": account.batch.batch_type,
                "priority": account.batch.priority,
                "warn_days": account.batch.warn_days,
                "expire_at": account.batch.expire_at.isoformat() if account.batch.expire_at else None,
            },
        }
    )


@bp.patch("/mobile-accounts/<int:account_id>/disable")
@require_session
@require_csrf
def disable_account(account_id: int):
    account = db.session.get(MobileAccount, account_id)
    if account is None:
        return error("ACC404", "账号不存在", status=404)
    if account.status == "disabled":
        return error("ACC409", "账号已禁用", status=409)
    payload = request.get_json(silent=True) or {}
    account.status = "disabled"
    account.disabled_reason = payload.get("reason", "manual_disable")
    write_audit("disable_account", "mobile_account", str(account_id), {"reason": account.disabled_reason})
    db.session.commit()
    return success({"id": account.id, "status": account.status})


@bp.patch("/mobile-accounts/<int:account_id>/enable")
@require_session
@require_csrf
def enable_account(account_id: int):
    account = db.session.get(MobileAccount, account_id)
    if account is None:
        return error("ACC404", "账号不存在", status=404)
    if account.status not in {"disabled", "expired"}:
        return error("ACC409", "当前状态不可恢复", status=409)
    account.status = "available"
    account.disabled_reason = None
    write_audit("enable_account", "mobile_account", str(account_id))
    db.session.commit()
    return success({"id": account.id, "status": account.status})


@bp.get("/mobile-accounts/<int:account_id>/history")
@require_session
def mobile_account_history(account_id: int):
    from ..models import BindingHistory

    rows = BindingHistory.query.filter(
        (BindingHistory.old_mobile_account_id == account_id) | (BindingHistory.new_mobile_account_id == account_id)
    ).order_by(BindingHistory.id.desc()).all()
    return success(
        {
            "items": [
                {
                    "id": row.id,
                    "student_id": row.student_id,
                    "action_type": row.action_type,
                    "old_mobile_account_id": row.old_mobile_account_id,
                    "new_mobile_account_id": row.new_mobile_account_id,
                    "created_at": row.created_at.isoformat(),
                }
                for row in rows
            ],
            "total": len(rows),
        }
    )


@bp.get("/batches")
@require_session
def list_batches():
    status_filter = request.args.get("status")
    query = AccountBatch.query
    if status_filter:
        query = query.filter(AccountBatch.status == status_filter)
    items = query.order_by(AccountBatch.priority.desc(), AccountBatch.id.desc()).all()
    return success(
        {
            "items": [
                {
                    "id": item.id,
                    "batch_code": item.batch_code,
                    "batch_name": item.batch_name,
                    "batch_type": item.batch_type,
                    "priority": item.priority,
                    "warn_days": item.warn_days,
                    "expire_at": item.expire_at.isoformat() if item.expire_at else None,
                    "status": item.status,
                    "remark": item.remark,
                }
                for item in items
            ],
            "total": len(items),
        }
    )


def _serialize_import_errors(job_id: int, limit: int = 20):
    rows = (
        ImportJobError.query.filter_by(import_job_id=job_id)
        .order_by(ImportJobError.row_no.asc(), ImportJobError.id.asc())
        .limit(limit)
        .all()
    )
    return [
        {
            "row_no": row.row_no,
            "field_name": row.field_name,
            "error_code": row.error_code,
            "error_message": row.error_message,
            "raw_data": row.raw_data,
        }
        for row in rows
    ]


@bp.post("/batches")
@require_session
@require_csrf
def create_batch():
    payload = request.get_json(silent=True) or {}
    batch_code = str(payload.get("batch_code") or "").strip()
    if not batch_code:
        return error("BAT400", "batch_code 不能为空", status=400)
    if AccountBatch.query.filter_by(batch_code=batch_code).first():
        return error("BAT409", "批次编码已存在", status=409)
    batch = AccountBatch(
        batch_code=batch_code,
        batch_name=payload.get("batch_name") or batch_code,
        batch_type=payload.get("batch_type") or "normal",
        priority=int(payload.get("priority") or 100),
        expire_at=normalize_date(payload.get("expire_at")),
        warn_days=int(payload.get("warn_days") or 1),
        status=payload.get("status") or "active",
        remark=payload.get("remark"),
    )
    db.session.add(batch)
    write_audit("create_batch", "account_batch", detail={"batch_code": batch.batch_code})
    db.session.commit()
    return success({"id": batch.id, "batch_code": batch.batch_code}, status=201)


@bp.put("/batches/<int:batch_id>")
@require_session
@require_csrf
def update_batch(batch_id: int):
    batch = db.session.get(AccountBatch, batch_id)
    if batch is None:
        return error("BAT404", "批次不存在", status=404)
    payload = request.get_json(silent=True) or {}
    if "batch_name" in payload:
        batch.batch_name = payload.get("batch_name") or batch.batch_code
    if "batch_type" in payload:
        batch.batch_type = payload["batch_type"]
    if "priority" in payload:
        batch.priority = int(payload["priority"])
    if "expire_at" in payload:
        batch.expire_at = normalize_date(payload.get("expire_at"))
    if "warn_days" in payload:
        batch.warn_days = int(payload["warn_days"])
    if "status" in payload:
        batch.status = payload["status"]
    if "remark" in payload:
        batch.remark = payload["remark"]
    write_audit("update_batch", "account_batch", str(batch.id), detail=payload)
    db.session.commit()
    return success(
        {
            "id": batch.id,
            "batch_code": batch.batch_code,
            "batch_name": batch.batch_name,
            "batch_type": batch.batch_type,
            "priority": batch.priority,
            "warn_days": batch.warn_days,
            "expire_at": batch.expire_at.isoformat() if batch.expire_at else None,
            "status": batch.status,
            "remark": batch.remark,
        }
    )
