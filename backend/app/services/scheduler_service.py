from __future__ import annotations

from datetime import date, timedelta

from flask import current_app
from sqlalchemy import select

from ..extensions import db
from ..models import AccountBatch, AlertRecord, BindingHistory, CurrentBinding, MobileAccount, SchedulerRunLog
from .config_service import get_config_value
from .date_service import utcnow
from .storage_service import cleanup_temp_files


def record_scheduler_run(job_name: str, status: str, message: str) -> SchedulerRunLog:
    log = SchedulerRunLog(job_name=job_name, status=status, message=message, started_at=utcnow(), finished_at=utcnow())
    db.session.add(log)
    db.session.commit()
    return log


def run_batch_expire_warning() -> str:
    today = date.today()
    batches = AccountBatch.query.filter(AccountBatch.status == "active", AccountBatch.expire_at.is_not(None)).all()
    count = 0
    for batch in batches:
        warn_days = batch.warn_days or int(get_config_value("batch.warn_days_default", 1) or 1)
        target_day = today + timedelta(days=int(warn_days))
        if batch.expire_at != target_day:
            continue
        exists = AlertRecord.query.filter_by(type="batch_expire", related_batch_id=batch.id, is_resolved=False).first()
        if exists:
            continue
        db.session.add(
            AlertRecord(
                type="batch_expire",
                level="warning",
                title="批次即将到期",
                content=f"批次 {batch.batch_code} 将于 {batch.expire_at.isoformat()} 到期",
                related_batch_id=batch.id,
            )
        )
        count += 1
    db.session.commit()
    record_scheduler_run("batch_expire_warning", "success", f"generated {count} alerts")
    return f"generated {count} alerts"


def run_binding_expire_release() -> str:
    bindings = db.session.execute(
        select(CurrentBinding).filter(CurrentBinding.expire_at < date.today()).with_for_update()
    ).scalars().all()
    released = 0
    for binding in bindings:
        account = db.session.execute(
            select(MobileAccount).filter_by(id=binding.mobile_account_id).with_for_update()
        ).scalar_one_or_none()
        if account:
            account.status = "available"
            account.disabled_reason = None
        db.session.add(
            BindingHistory(
                student_id=binding.student_id,
                old_mobile_account_id=binding.mobile_account_id,
                new_mobile_account_id=None,
                action_type="release",
                old_expire_at=binding.expire_at,
                new_expire_at=binding.expire_at,
                detail_json={"reason": "binding_expire_release"},
            )
        )
        db.session.delete(binding)
        released += 1
    db.session.commit()
    record_scheduler_run("binding_expire_release", "success", f"released {released} bindings")
    return f"released {released} bindings"


def run_inventory_alert_scan() -> str:
    threshold = int(get_config_value("inventory.low_stock_threshold", 50) or 50)
    available_count = MobileAccount.query.filter_by(status="available").count()
    if available_count < threshold and not AlertRecord.query.filter_by(type="inventory_low", is_resolved=False).first():
        db.session.add(
            AlertRecord(
                type="inventory_low",
                level="warning",
                title="移动账号库存不足",
                content=f"当前可用账号数 {available_count}，低于阈值 {threshold}",
            )
        )
        db.session.commit()
    record_scheduler_run("inventory_alert_scan", "success", f"available={available_count}, threshold={threshold}")
    return f"available={available_count}, threshold={threshold}"


def run_cleanup_temp_files() -> str:
    keep_days = int(get_config_value("storage.cleanup_days", 7) or 7)
    removed = cleanup_temp_files(current_app.config["STORAGE_ROOT"], keep_days)
    record_scheduler_run("cleanup_temp_files", "success", f"removed={removed}")
    return f"removed={removed}"


JOB_RUNNERS = {
    "batch_expire_warning": run_batch_expire_warning,
    "binding_expire_release": run_binding_expire_release,
    "inventory_alert_scan": run_inventory_alert_scan,
    "cleanup_temp_files": run_cleanup_temp_files,
}
