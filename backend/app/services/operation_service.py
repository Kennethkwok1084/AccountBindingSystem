from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from ..auth import current_user
from ..extensions import db
from ..models import (
    AccountBatch,
    AlertRecord,
    BindingHistory,
    CurrentBinding,
    ImportJob,
    ImportJobError,
    MobileAccount,
    OperationBatch,
    OperationBatchDetail,
    Student,
)
from .audit_service import write_audit
from .config_service import get_config_value, set_config_value
from .date_service import compute_expire_from, normalize_date, normalize_datetime, utcnow
from .excel_service import validate_excel
from .export_service import create_export
from .serialization_service import to_jsonable
from .storage_service import save_upload


MAX_IMPORT_ERRORS_PAGE_SIZE = 200


@dataclass
class CandidateInfo:
    account_id: int | None
    account: str | None
    message: str


def preview_charge_batch(file):
    user = current_user()
    stored_path, checksum = save_upload(file, "charge_list")
    import_job = ImportJob(
        job_type="charge_list",
        original_filename=file.filename or "charge_list.xlsx",
        stored_path=stored_path,
        file_checksum=checksum,
        operator_id=user.id,
        status="validating",
    )
    db.session.add(import_job)
    db.session.flush()

    parse_result = validate_excel(stored_path, "charge_list")
    _persist_import_issues(import_job.id, parse_result.issues)
    import_job.sheet_name = parse_result.sheet_name
    import_job.mapping_json = {"columns": sorted(parse_result.available_columns)}
    if parse_result.has_fatal_errors:
        import_job.status = "failed"
        import_job.error_summary = "收费清单模板校验失败"
        import_job.failed_rows = len(parse_result.issues)
        import_job.finished_at = utcnow()
        db.session.commit()
        return None, import_job

    last_processed = normalize_datetime(get_config_value("charge.last_processed_charge_time"))
    rows = []
    for row_no, row in enumerate(parse_result.rows, start=2):
        charge_time = row["charge_time"]
        if last_processed and charge_time <= last_processed:
            continue
        rows.append((row_no, row, charge_time))
    rows.sort(key=lambda item: (item[2], item[0]))

    operation_batch = OperationBatch(
        batch_type="charge_batch",
        status="previewed",
        source_import_job_id=import_job.id,
        total_rows=len(rows),
        operator_id=user.id,
        last_processed_charge_time_before=last_processed,
    )
    db.session.add(operation_batch)
    db.session.flush()

    max_execute_rows = int(get_config_value("charge.max_execute_rows", 20) or 20)
    preview_details = []
    for index, (row_no, row, charge_time) in enumerate(rows, start=1):
        student_no = row["student_no"]
        student = db.session.execute(select(Student).filter_by(student_no=student_no)).scalar_one_or_none()
        binding = _get_binding(student.id) if student else None

        action_plan = "fail"
        result_message = ""
        new_expire_at = None
        suggested_account = None

        if index > max_execute_rows:
            result_message = f"超出本次允许处理的前 {max_execute_rows} 人"
        elif binding is None:
            action_plan = "allocate"
            new_expire_at = compute_expire_from(charge_time.date(), row.get("package_name"))
            suggested_account = _preview_candidate()
            if suggested_account is None:
                action_plan = "fail"
                result_message = "当前无可用移动账号"
            else:
                result_message = f"计划新分配账号 {suggested_account.account}"
        elif binding.expire_at >= charge_time.date():
            action_plan = "renew"
            base_date = max(binding.expire_at, charge_time.date())
            new_expire_at = compute_expire_from(base_date, row.get("package_name"))
            result_message = "当前账号仍有效，计划顺延有效期"
        else:
            action_plan = "rebind"
            new_expire_at = compute_expire_from(charge_time.date(), row.get("package_name"))
            old_account = db.session.get(MobileAccount, binding.mobile_account_id)
            suggested_account = _preview_candidate(exclude_batch_id=old_account.batch_id if old_account else None)
            if suggested_account is None:
                action_plan = "fail"
                result_message = "当前无可用于换绑的新账号"
            else:
                old_account_name = old_account.account if old_account else "-"
                result_message = f"计划从 {old_account_name} 换绑到 {suggested_account.account}"

        detail = OperationBatchDetail(
            operation_batch_id=operation_batch.id,
            row_no=row_no,
            student_id=student.id if student else None,
            student_no=student_no,
            student_name=row["name"],
            action_plan=action_plan,
            status="previewed" if action_plan != "fail" else "failed",
            old_mobile_account_id=binding.mobile_account_id if binding else None,
            new_mobile_account_id=suggested_account.id if suggested_account else None,
            old_expire_at=binding.expire_at if binding else None,
            new_expire_at=new_expire_at,
            charge_time=charge_time,
            package_name=row["package_name"],
            fee_amount=Decimal(str(row["fee_amount"])),
            result_message=result_message,
            raw_payload=_jsonable(row),
        )
        db.session.add(detail)
        preview_details.append(detail)

    import_job.status = "validated" if parse_result.issues else "success"
    import_job.total_rows = len(rows) + len(parse_result.issues)
    import_job.success_rows = len(preview_details)
    import_job.failed_rows = len(parse_result.issues)
    import_job.finished_at = utcnow()
    db.session.commit()
    return operation_batch, import_job


def execute_charge_batch(batch_id: int, idempotency_key: str):
    operation_batch = _lock_operation_batch(batch_id)
    _ensure_execute_ready(operation_batch, idempotency_key)

    details = db.session.execute(
        select(OperationBatchDetail)
        .filter_by(operation_batch_id=batch_id)
        .order_by(OperationBatchDetail.row_no.asc())
    ).scalars().all()

    success_count = 0
    fail_count = 0
    executed_charge_times = []
    export_rows = []
    operation_batch.status = "executing"

    for detail in details:
        if detail.action_plan == "fail":
            detail.status = "failed"
            fail_count += 1
            continue
        try:
            with db.session.begin_nested():
                export_row, charge_time = _execute_charge_detail(detail)
                if export_row is not None:
                    export_rows.append(export_row)
                if charge_time is not None:
                    executed_charge_times.append(charge_time)
                detail.status = "success"
                detail.result_message = "执行成功"
                success_count += 1
        except Exception as exc:  # noqa: BLE001
            detail.status = "failed"
            detail.result_message = str(exc)
            fail_count += 1

    if executed_charge_times:
        latest = max(executed_charge_times)
        operation_batch.last_processed_charge_time_after = latest
        set_config_value("charge.last_processed_charge_time", latest.isoformat(sep=" "), commit=False)
    _finalize_operation_batch(operation_batch, success_count, fail_count)
    write_audit(
        "execute_charge_batch",
        "operation_batch",
        str(operation_batch.id),
        {"success_rows": success_count, "failed_rows": fail_count},
    )
    db.session.commit()
    export_job = _create_export_after_commit(operation_batch.id, export_rows)
    return operation_batch, export_job


def preview_full_students(file):
    user = current_user()
    stored_path, checksum = save_upload(file, "full_student_list")
    import_job = ImportJob(
        job_type="full_student_list",
        original_filename=file.filename or "full_students.xlsx",
        stored_path=stored_path,
        file_checksum=checksum,
        operator_id=user.id,
        status="validating",
    )
    db.session.add(import_job)
    db.session.flush()

    parse_result = validate_excel(stored_path, "full_student_list")
    _persist_import_issues(import_job.id, parse_result.issues)
    import_job.sheet_name = parse_result.sheet_name
    import_job.mapping_json = {"columns": sorted(parse_result.available_columns)}
    if parse_result.has_fatal_errors:
        import_job.status = "failed"
        import_job.error_summary = "完整名单模板校验失败"
        import_job.failed_rows = len(parse_result.issues)
        import_job.finished_at = utcnow()
        db.session.commit()
        return None, import_job

    preview_rows = []
    release_count = 0
    conflict_count = 0
    checks_account_conflict = "mobile_account" in parse_result.available_columns

    for row_no, row in enumerate(parse_result.rows, start=2):
        student = db.session.execute(select(Student).filter_by(student_no=row["student_no"])).scalar_one_or_none()
        binding = _get_binding(student.id) if student else None
        conflict = False
        if checks_account_conflict and binding and row.get("mobile_account"):
            bound_account = db.session.get(MobileAccount, binding.mobile_account_id)
            conflict = bool(bound_account and bound_account.account != row["mobile_account"])
        if row["expire_at"] and row["expire_at"] < date.today():
            release_count += 1
        if conflict:
            conflict_count += 1
        preview_rows.append(
            {
                "row_no": row_no,
                "student_no": row["student_no"],
                "name": row["name"],
                "expire_at": row["expire_at"].isoformat(),
                "conflict": conflict,
                "conflict_message": "名单账号与系统当前绑定不一致" if conflict else "",
            }
        )

    import_job.status = "validated" if parse_result.issues else "success"
    import_job.total_rows = len(parse_result.rows) + len(parse_result.issues)
    import_job.success_rows = len(parse_result.rows)
    import_job.failed_rows = len(parse_result.issues)
    import_job.finished_at = utcnow()
    db.session.commit()
    return {"preview": preview_rows, "release_count": release_count, "conflict_count": conflict_count}, import_job


def execute_full_students(job_id: int, idempotency_key: str):
    import_job = db.session.get(ImportJob, job_id)
    if import_job is None:
        raise LookupError("导入任务不存在")
    existing_batch = db.session.execute(
        select(OperationBatch).filter(
            OperationBatch.batch_type == "full_student_sync",
            OperationBatch.source_import_job_id == import_job.id,
            OperationBatch.status.in_(("executing", "success", "partial_success")),
        )
    ).scalar_one_or_none()
    if existing_batch is not None:
        raise ValueError("该完整名单导入任务已执行，禁止重复执行")

    parse_result = validate_excel(import_job.stored_path, "full_student_list")
    if parse_result.has_fatal_errors:
        raise ValueError("完整名单模板校验失败")

    operation_batch = OperationBatch(
        batch_type="full_student_sync",
        status="previewed",
        source_import_job_id=import_job.id,
        operator_id=current_user().id,
    )
    db.session.add(operation_batch)
    db.session.flush()
    _ensure_execute_ready(operation_batch, idempotency_key, is_new_batch=True)

    success_rows = 0
    released_rows = 0
    conflict_rows = 0
    checks_account_conflict = "mobile_account" in parse_result.available_columns

    for index, row in enumerate(parse_result.rows, start=1):
        detail = OperationBatchDetail(
            operation_batch_id=operation_batch.id,
            row_no=index,
            student_no=row["student_no"],
            student_name=row["name"],
            action_plan="sync",
            status="previewed",
            new_expire_at=row["expire_at"],
            raw_payload=_jsonable(row),
        )
        db.session.add(detail)
        try:
            with db.session.begin_nested():
                released, conflict = _execute_full_student_detail(detail, row, checks_account_conflict)
                if conflict:
                    conflict_rows += 1
                    detail.status = "failed"
                    detail.result_message = "名单账号与系统当前绑定不一致，已生成告警"
                else:
                    success_rows += 1
                    if released:
                        released_rows += 1
                    detail.status = "success"
                    detail.result_message = "执行成功"
        except Exception as exc:  # noqa: BLE001
            detail.status = "failed"
            detail.result_message = str(exc)
            conflict_rows += 1

    import_job.status = "success" if conflict_rows == 0 else "partial_success"
    import_job.success_rows = success_rows
    import_job.failed_rows = conflict_rows
    import_job.finished_at = utcnow()
    _finalize_operation_batch(operation_batch, success_rows, conflict_rows)
    write_audit(
        "execute_full_students",
        "import_job",
        str(import_job.id),
        {"released_rows": released_rows, "conflicts": conflict_rows},
    )
    db.session.commit()
    return {
        "operation_batch_id": operation_batch.id,
        "success_rows": success_rows,
        "released_rows": released_rows,
        "conflicts": conflict_rows,
    }


def manual_rebind(student_no: str, new_account_id: int, old_account_action: str, remark: str | None, idempotency_key: str):
    student = db.session.execute(select(Student).filter_by(student_no=student_no)).scalar_one_or_none()
    if student is None:
        raise LookupError("学号不存在")

    operation_batch = OperationBatch(
        batch_type="manual_rebind",
        status="previewed",
        operator_id=current_user().id,
        total_rows=1,
    )
    db.session.add(operation_batch)
    db.session.flush()
    _ensure_execute_ready(operation_batch, idempotency_key, is_new_batch=True)

    detail = OperationBatchDetail(
        operation_batch_id=operation_batch.id,
        row_no=1,
        student_id=student.id,
        student_no=student.student_no,
        student_name=student.name,
        action_plan="rebind",
        status="previewed",
        raw_payload=_jsonable({"remark": remark, "old_account_action": old_account_action, "new_account_id": new_account_id}),
    )
    db.session.add(detail)

    with db.session.begin_nested():
        binding = _get_binding(student.id, for_update=True)
        if binding is None:
            raise LookupError("当前未找到有效绑定")
        old_account = db.session.execute(
            select(MobileAccount).filter_by(id=binding.mobile_account_id).with_for_update()
        ).scalar_one()
        new_account = db.session.execute(
            select(MobileAccount).filter_by(id=new_account_id).with_for_update()
        ).scalar_one_or_none()
        if new_account is None:
            raise LookupError("新账号不存在")
        if new_account.status != "available":
            raise ValueError("新账号不可用")

        if old_account_action == "disable":
            old_account.status = "disabled"
            old_account.disabled_reason = remark or "manual_rebind"
        elif old_account_action == "release":
            old_account.status = "available"
            old_account.disabled_reason = None
        else:
            raise ValueError("old_account_action 仅支持 disable 或 release")

        new_account.status = "assigned"
        new_account.last_assigned_at = utcnow()
        db.session.add(
            BindingHistory(
                student_id=student.id,
                old_mobile_account_id=old_account.id,
                new_mobile_account_id=new_account.id,
                action_type="manual_fix",
                old_expire_at=binding.expire_at,
                new_expire_at=binding.expire_at,
                detail_json={"remark": remark, "old_account_action": old_account_action},
            )
        )
        binding.mobile_account_id = new_account.id
        binding.bind_source = "manual"
        binding.bind_type = "manual_fix"
        binding.bind_at = utcnow()

        detail.old_mobile_account_id = old_account.id
        detail.new_mobile_account_id = new_account.id
        detail.old_expire_at = binding.expire_at
        detail.new_expire_at = binding.expire_at
        detail.status = "success"
        detail.result_message = "执行成功"
        detail.export_included = True

    _finalize_operation_batch(operation_batch, 1, 0)
    write_audit("manual_rebind", "student", str(student.id), {"new_account_id": new_account.id})
    db.session.commit()
    export_job = _create_export_after_commit(operation_batch.id, [{"学号": student.student_no, "移动账户": new_account.account}])
    return operation_batch, student, old_account, new_account, export_job


def preview_batch_rebind(batch_id: int):
    batch = db.session.get(AccountBatch, batch_id)
    if batch is None:
        raise LookupError("批次不存在")
    rows = []
    affected = (
        db.session.execute(
            select(CurrentBinding, Student, MobileAccount)
            .join(Student, Student.id == CurrentBinding.student_id)
            .join(MobileAccount, MobileAccount.id == CurrentBinding.mobile_account_id)
            .filter(MobileAccount.batch_id == batch.id)
        )
        .all()
    )
    for binding, student, old_account in affected:
        candidate = _preview_candidate(exclude_batch_id=batch.id)
        rows.append(
            {
                "student_no": student.student_no,
                "name": student.name,
                "old_account": old_account.account,
                "expire_at": binding.expire_at.isoformat(),
                "new_account": candidate.account if candidate else None,
                "can_execute": candidate is not None,
                "message": "可换绑" if candidate else "无可用新账号",
            }
        )
    return batch, rows


def execute_batch_rebind(batch_id: int, idempotency_key: str):
    batch = db.session.get(AccountBatch, batch_id)
    if batch is None:
        raise LookupError("批次不存在")

    operation_batch = OperationBatch(
        batch_type="batch_rebind",
        status="previewed",
        operator_id=current_user().id,
    )
    db.session.add(operation_batch)
    db.session.flush()
    _ensure_execute_ready(operation_batch, idempotency_key, is_new_batch=True)

    export_rows = []
    success_rows = 0
    failed_rows = 0
    affected = (
        db.session.execute(
            select(CurrentBinding, Student, MobileAccount)
            .join(Student, Student.id == CurrentBinding.student_id)
            .join(MobileAccount, MobileAccount.id == CurrentBinding.mobile_account_id)
            .filter(MobileAccount.batch_id == batch.id)
        )
        .all()
    )

    for index, (binding, student, old_account) in enumerate(affected, start=1):
        detail = OperationBatchDetail(
            operation_batch_id=operation_batch.id,
            row_no=index,
            student_id=student.id,
            student_no=student.student_no,
            student_name=student.name,
            action_plan="rebind",
            status="previewed",
            old_mobile_account_id=old_account.id,
            old_expire_at=binding.expire_at,
            new_expire_at=binding.expire_at,
            result_message="待执行",
            raw_payload=_jsonable({"reason": "batch_expire"}),
        )
        db.session.add(detail)
        try:
            with db.session.begin_nested():
                locked_binding = _get_binding(student.id, for_update=True)
                if locked_binding is None:
                    raise ValueError("当前绑定已不存在")
                locked_old_account = db.session.execute(
                    select(MobileAccount).filter_by(id=locked_binding.mobile_account_id).with_for_update()
                ).scalar_one()
                candidate = _reserve_candidate(exclude_batch_id=batch.id)
                if candidate is None:
                    raise ValueError("无可用新账号")

                candidate.status = "assigned"
                candidate.last_assigned_at = utcnow()
                locked_old_account.status = "expired"
                db.session.add(
                    BindingHistory(
                        student_id=student.id,
                        old_mobile_account_id=locked_old_account.id,
                        new_mobile_account_id=candidate.id,
                        action_type="rebind",
                        old_expire_at=locked_binding.expire_at,
                        new_expire_at=locked_binding.expire_at,
                        detail_json={"reason": "batch_expire"},
                    )
                )
                locked_binding.mobile_account_id = candidate.id
                locked_binding.bind_source = "batch_rebind"
                locked_binding.bind_type = "rebind"
                locked_binding.bind_at = utcnow()

                detail.new_mobile_account_id = candidate.id
                detail.status = "success"
                detail.result_message = "执行成功"
                detail.export_included = True
                export_rows.append({"学号": student.student_no, "移动账户": candidate.account})
                success_rows += 1
        except Exception as exc:  # noqa: BLE001
            detail.status = "failed"
            detail.result_message = str(exc)
            failed_rows += 1

    _finalize_operation_batch(operation_batch, success_rows, failed_rows)
    write_audit(
        "execute_batch_rebind",
        "account_batch",
        str(batch.id),
        {"success_rows": success_rows, "failed_rows": failed_rows},
    )
    db.session.commit()
    export_job = _create_export_after_commit(operation_batch.id, export_rows)
    return operation_batch, export_job


def get_import_job_detail(job_id: int, page: int = 1, page_size: int = 50):
    page_size = max(1, min(page_size, MAX_IMPORT_ERRORS_PAGE_SIZE))
    import_job = db.session.get(ImportJob, job_id)
    if import_job is None:
        raise LookupError("导入任务不存在")

    error_query = ImportJobError.query.filter_by(import_job_id=job_id).order_by(ImportJobError.row_no.asc(), ImportJobError.id.asc())
    pagination = error_query.paginate(page=page, per_page=page_size, error_out=False)
    return {
        "job": {
            "id": import_job.id,
            "job_type": import_job.job_type,
            "original_filename": import_job.original_filename,
            "stored_path": import_job.stored_path,
            "file_checksum": import_job.file_checksum,
            "sheet_name": import_job.sheet_name,
            "mapping_json": import_job.mapping_json,
            "status": import_job.status,
            "total_rows": import_job.total_rows,
            "success_rows": import_job.success_rows,
            "failed_rows": import_job.failed_rows,
            "error_summary": import_job.error_summary,
            "started_at": import_job.started_at.isoformat(),
            "finished_at": import_job.finished_at.isoformat() if import_job.finished_at else None,
        },
        "errors": {
            "items": [
                {
                    "id": item.id,
                    "row_no": item.row_no,
                    "field_name": item.field_name,
                    "error_code": item.error_code,
                    "error_message": item.error_message,
                    "raw_data": item.raw_data,
                }
                for item in pagination.items
            ],
            "page": page,
            "page_size": page_size,
            "total": pagination.total,
        },
    }


def _execute_charge_detail(detail: OperationBatchDetail):
    student = _find_or_create_student(detail.student_no or "", detail.student_name)
    binding = _get_binding(student.id, for_update=True)
    charge_time = detail.charge_time
    if charge_time is None:
        raise ValueError("charge_time 缺失")

    student.last_charge_time = charge_time
    student.current_package_name = detail.package_name
    student.current_fee_amount = detail.fee_amount
    student.expected_expire_at = detail.new_expire_at
    detail.student_id = student.id
    payload = _jsonable(detail.raw_payload)

    if detail.action_plan == "allocate":
        if binding is not None:
            raise ValueError("学生已存在当前绑定，无法按预览结果执行新分配")
        candidate = _reserve_candidate()
        if candidate is None:
            raise ValueError("当前无可用移动账号")
        candidate.status = "assigned"
        candidate.last_assigned_at = utcnow()
        binding = CurrentBinding(
            student_id=student.id,
            mobile_account_id=candidate.id,
            bind_source="charge_import",
            bind_type="allocate",
            bind_at=utcnow(),
            expire_at=detail.new_expire_at,
        )
        db.session.add(binding)
        db.session.add(
            BindingHistory(
                student_id=student.id,
                new_mobile_account_id=candidate.id,
                action_type="allocate",
                new_expire_at=detail.new_expire_at,
                detail_json=payload,
            )
        )
        detail.new_mobile_account_id = candidate.id
        detail.export_included = True
        return {"学号": student.student_no, "移动账户": candidate.account}, charge_time

    if detail.action_plan == "renew":
        if binding is None:
            raise ValueError("续费时未找到当前绑定")
        old_expire_at = binding.expire_at
        binding.expire_at = detail.new_expire_at
        db.session.add(
            BindingHistory(
                student_id=student.id,
                old_mobile_account_id=binding.mobile_account_id,
                new_mobile_account_id=binding.mobile_account_id,
                action_type="renew",
                old_expire_at=old_expire_at,
                new_expire_at=detail.new_expire_at,
                detail_json=payload,
            )
        )
        return None, charge_time

    if detail.action_plan == "rebind":
        if binding is None:
            raise ValueError("换绑时未找到当前绑定")
        old_account = db.session.execute(
            select(MobileAccount).filter_by(id=binding.mobile_account_id).with_for_update()
        ).scalar_one()
        candidate = _reserve_candidate(exclude_batch_id=old_account.batch_id)
        if candidate is None:
            raise ValueError("当前无可用于换绑的新账号")
        candidate.status = "assigned"
        candidate.last_assigned_at = utcnow()
        old_account.status = "available"
        old_account.disabled_reason = None
        db.session.add(
            BindingHistory(
                student_id=student.id,
                old_mobile_account_id=old_account.id,
                new_mobile_account_id=candidate.id,
                action_type="rebind",
                old_expire_at=binding.expire_at,
                new_expire_at=detail.new_expire_at,
                detail_json=payload,
            )
        )
        binding.mobile_account_id = candidate.id
        binding.bind_source = "charge_import"
        binding.bind_type = "rebind"
        binding.bind_at = utcnow()
        binding.expire_at = detail.new_expire_at
        detail.new_mobile_account_id = candidate.id
        detail.export_included = True
        return {"学号": student.student_no, "移动账户": candidate.account}, charge_time

    raise ValueError("不支持的执行动作")


def _execute_full_student_detail(detail: OperationBatchDetail, row: dict, checks_account_conflict: bool) -> tuple[bool, bool]:
    student = _find_or_create_student(row["student_no"], row["name"])
    student.source_expire_at = row["expire_at"]
    detail.student_id = student.id
    detail.student_name = student.name

    binding = _get_binding(student.id, for_update=True)
    if binding is None:
        return False, False

    old_account = db.session.execute(
        select(MobileAccount).filter_by(id=binding.mobile_account_id).with_for_update()
    ).scalar_one()

    if checks_account_conflict and row.get("mobile_account") and old_account.account != row["mobile_account"]:
        db.session.add(
            AlertRecord(
                type="binding_conflict",
                level="warning",
                title="完整名单与当前绑定不一致",
                content=f"学号 {student.student_no} 在完整名单中的账号与系统当前绑定不一致",
                related_student_id=student.id,
            )
        )
        return False, True

    old_expire_at = binding.expire_at
    binding.expire_at = row["expire_at"]
    detail.old_mobile_account_id = old_account.id
    detail.new_mobile_account_id = old_account.id
    detail.old_expire_at = old_expire_at
    detail.new_expire_at = row["expire_at"]

    if row["expire_at"] < date.today():
        old_account.status = "available"
        old_account.disabled_reason = None
        db.session.add(
            BindingHistory(
                student_id=student.id,
                old_mobile_account_id=old_account.id,
                new_mobile_account_id=None,
                action_type="release",
                old_expire_at=old_expire_at,
                new_expire_at=row["expire_at"],
                detail_json={"reason": "full_student_list"},
            )
        )
        db.session.delete(binding)
        return True, False

    db.session.add(
        BindingHistory(
            student_id=student.id,
            old_mobile_account_id=old_account.id,
            new_mobile_account_id=old_account.id,
            action_type="sync_expire_at",
            old_expire_at=old_expire_at,
            new_expire_at=row["expire_at"],
            detail_json={"reason": "full_student_list"},
        )
    )
    return False, False


def _lock_operation_batch(batch_id: int) -> OperationBatch:
    batch = db.session.execute(
        select(OperationBatch).filter_by(id=batch_id).with_for_update()
    ).scalar_one_or_none()
    if batch is None:
        raise LookupError("操作批次不存在")
    return batch


def _ensure_execute_ready(operation_batch: OperationBatch, idempotency_key: str | None, is_new_batch: bool = False) -> None:
    if not idempotency_key:
        raise ValueError("缺少 X-Idempotency-Key")

    existing = db.session.execute(
        select(OperationBatch)
        .filter(OperationBatch.id != operation_batch.id, OperationBatch.idempotency_key == idempotency_key)
    ).scalar_one_or_none()
    if existing is not None:
        raise ValueError("幂等键已被其他批次使用")

    if operation_batch.idempotency_key and operation_batch.idempotency_key != idempotency_key:
        raise ValueError("该批次已绑定其他幂等键")
    if operation_batch.status in {"executing", "success", "partial_success"} and not is_new_batch:
        raise ValueError("该批次不可重复执行")

    operation_batch.idempotency_key = idempotency_key


def _finalize_operation_batch(operation_batch: OperationBatch, success_rows: int, failed_rows: int) -> None:
    operation_batch.success_rows = success_rows
    operation_batch.failed_rows = failed_rows
    operation_batch.total_rows = success_rows + failed_rows if operation_batch.total_rows == 0 else operation_batch.total_rows
    operation_batch.executed_at = utcnow()
    operation_batch.status = "success" if failed_rows == 0 else "partial_success"


def _reserve_candidate(exclude_batch_id: int | None = None):
    query = (
        select(MobileAccount)
        .join(AccountBatch, AccountBatch.id == MobileAccount.batch_id)
        .filter(MobileAccount.status == "available", AccountBatch.status == "active")
        .order_by(AccountBatch.priority.desc(), AccountBatch.id.desc(), MobileAccount.id.asc())
        .with_for_update()
    )
    if exclude_batch_id is not None:
        query = query.filter(MobileAccount.batch_id != exclude_batch_id)
    return db.session.execute(query).scalars().first()


def _preview_candidate(exclude_batch_id: int | None = None):
    query = (
        select(MobileAccount)
        .join(AccountBatch, AccountBatch.id == MobileAccount.batch_id)
        .filter(MobileAccount.status == "available", AccountBatch.status == "active")
        .order_by(AccountBatch.priority.desc(), AccountBatch.id.desc(), MobileAccount.id.asc())
    )
    if exclude_batch_id is not None:
        query = query.filter(MobileAccount.batch_id != exclude_batch_id)
    return db.session.execute(query).scalars().first()


def _find_or_create_student(student_no: str, name: str | None):
    student = db.session.execute(select(Student).filter_by(student_no=student_no)).scalar_one_or_none()
    if student is None:
        student = Student(student_no=student_no, name=name)
        db.session.add(student)
        db.session.flush()
    elif name:
        student.name = name
    return student


def _get_binding(student_id: int, for_update: bool = False):
    query = select(CurrentBinding).filter_by(student_id=student_id)
    if for_update:
        query = query.with_for_update()
    return db.session.execute(query).scalar_one_or_none()


def _persist_import_issues(import_job_id: int, issues) -> None:
    for issue in issues:
        db.session.add(
            ImportJobError(
                import_job_id=import_job_id,
                row_no=issue.row_no,
                field_name=issue.field_name,
                error_code=issue.error_code,
                error_message=issue.error_message,
                raw_data=to_jsonable(issue.raw_data),
            )
        )


def _create_export_after_commit(operation_batch_id: int, rows: list[dict]):
    if not rows:
        return None
    export_job = create_export(operation_batch_id, rows)
    db.session.commit()
    return export_job


def _jsonable(value):
    return to_jsonable(value)
