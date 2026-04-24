from __future__ import annotations

from flask import Blueprint, request
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import aliased

from ..extensions import db
from ..models import BindingHistory, CurrentBinding, MobileAccount, Student
from ..responses import error, success
from ..security import require_csrf, require_session
from ..services.export_service import create_tabular_export


bp = Blueprint("students", __name__)


ACTION_TYPE_LABELS = {
    "allocate": "分配新账号",
    "renew": "续费",
    "rebind": "换绑",
    "release": "释放绑定",
    "sync_bind": "按名单绑定",
    "sync_rebind": "按名单换绑",
    "sync_expire_at": "同步到期时间",
    "manual_fix": "手工修正",
}


def _bool_arg(value: str | None):
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return None
    return str(value).lower() == "true"


def _paging_from_request(default_page_size: int = 50):
    from flask import request

    page = max(1, int(request.args.get("page", 1) or 1))
    page_size = max(1, min(int(request.args.get("page_size", default_page_size) or default_page_size), 200))
    return page, page_size


def _sort_direction(sort_order: str):
    return desc if str(sort_order).lower() == "desc" else asc


def _student_history_query(student_id: int, action_type: str | None):
    query = BindingHistory.query.filter_by(student_id=student_id)
    if action_type:
        query = query.filter(BindingHistory.action_type == action_type)
    return query


def _student_history_order(sort_by: str, sort_order: str):
    sortable_columns = {
        "id": BindingHistory.id,
        "created_at": BindingHistory.created_at,
        "action_type": BindingHistory.action_type,
        "old_mobile_account_id": BindingHistory.old_mobile_account_id,
        "new_mobile_account_id": BindingHistory.new_mobile_account_id,
    }
    order_column = sortable_columns.get(sort_by, BindingHistory.created_at)
    direction = _sort_direction(sort_order)
    return direction, order_column


def _account_history_query(account_id: int, action_type: str | None):
    query = BindingHistory.query.filter(
        (BindingHistory.old_mobile_account_id == account_id) | (BindingHistory.new_mobile_account_id == account_id)
    )
    if action_type:
        query = query.filter(BindingHistory.action_type == action_type)
    return query


def _account_history_order(sort_by: str, sort_order: str):
    sortable_columns = {
        "id": BindingHistory.id,
        "created_at": BindingHistory.created_at,
        "action_type": BindingHistory.action_type,
        "student_id": BindingHistory.student_id,
    }
    order_column = sortable_columns.get(sort_by, BindingHistory.created_at)
    direction = _sort_direction(sort_order)
    return direction, order_column


@bp.get("/students")
@require_session
def students():
    from flask import request

    keyword = str(request.args.get("keyword") or "").strip()
    has_binding = _bool_arg(request.args.get("has_binding"))
    sort_by = request.args.get("sort_by", "id")
    sort_order = request.args.get("sort_order", "asc")
    page, page_size = _paging_from_request()

    def apply_filters(stmt):
        if keyword:
            stmt = stmt.where(
                or_(
                    Student.student_no.ilike(f"%{keyword}%"),
                    Student.name.ilike(f"%{keyword}%"),
                )
            )
        if has_binding is True:
            stmt = stmt.where(CurrentBinding.id.is_not(None))
        elif has_binding is False:
            stmt = stmt.where(CurrentBinding.id.is_(None))
        return stmt

    sortable_columns = {
        "id": Student.id,
        "student_no": Student.student_no,
        "name": Student.name,
        "expected_expire_at": Student.expected_expire_at,
        "source_expire_at": Student.source_expire_at,
        "current_mobile_account": MobileAccount.account,
        "current_binding_expire_at": CurrentBinding.expire_at,
    }
    order_column = sortable_columns.get(sort_by, Student.id)
    direction = _sort_direction(sort_order)

    count_stmt = apply_filters(
        select(func.count(Student.id))
        .select_from(Student)
        .outerjoin(CurrentBinding, CurrentBinding.student_id == Student.id)
        .outerjoin(MobileAccount, MobileAccount.id == CurrentBinding.mobile_account_id)
    )
    total = db.session.execute(count_stmt).scalar_one()

    rows = db.session.execute(
        apply_filters(
            select(Student, CurrentBinding, MobileAccount)
            .outerjoin(CurrentBinding, CurrentBinding.student_id == Student.id)
            .outerjoin(MobileAccount, MobileAccount.id == CurrentBinding.mobile_account_id)
        )
        .order_by(direction(order_column), Student.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return success(
        {
            "items": [
                {
                    "id": student.id,
                    "student_no": student.student_no,
                    "name": student.name,
                    "expected_expire_at": student.expected_expire_at.isoformat() if student.expected_expire_at else None,
                    "source_expire_at": student.source_expire_at.isoformat() if student.source_expire_at else None,
                    "current_mobile_account": account.account if account else None,
                    "current_binding_expire_at": binding.expire_at.isoformat() if binding else None,
                }
                for student, binding, account in rows
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@bp.post("/students/export")
@require_session
@require_csrf
def export_students():
    payload = request.get_json(silent=True) or {}
    keyword = str(payload.get("keyword") or "").strip()
    has_binding = _bool_arg(payload.get("has_binding"))
    sort_by = payload.get("sort_by", "student_no")
    sort_order = payload.get("sort_order", "asc")

    def apply_filters(stmt):
        if keyword:
            stmt = stmt.where(
                or_(
                    Student.student_no.ilike(f"%{keyword}%"),
                    Student.name.ilike(f"%{keyword}%"),
                )
            )
        if has_binding is True:
            stmt = stmt.where(CurrentBinding.id.is_not(None))
        elif has_binding is False:
            stmt = stmt.where(CurrentBinding.id.is_(None))
        return stmt

    sortable_columns = {
        "id": Student.id,
        "student_no": Student.student_no,
        "name": Student.name,
        "expected_expire_at": Student.expected_expire_at,
        "source_expire_at": Student.source_expire_at,
        "current_mobile_account": MobileAccount.account,
        "current_binding_expire_at": CurrentBinding.expire_at,
    }
    order_column = sortable_columns.get(sort_by, Student.id)
    direction = _sort_direction(sort_order)
    rows = db.session.execute(
        apply_filters(
            select(Student, CurrentBinding, MobileAccount)
            .outerjoin(CurrentBinding, CurrentBinding.student_id == Student.id)
            .outerjoin(MobileAccount, MobileAccount.id == CurrentBinding.mobile_account_id)
        ).order_by(direction(order_column), Student.id.asc())
    ).all()
    if not rows:
        return error("EXP422", "当前筛选条件下没有可导出的学生台账数据", status=422)

    export_job = create_tabular_export(
        None,
        [
            {
                "学号": student.student_no,
                "姓名": student.name or "",
                "当前账号": account.account if account else "",
                "绑定到期": binding.expire_at.isoformat() if binding else "",
                "来源到期": student.source_expire_at.isoformat() if student.source_expire_at else "",
                "预期到期": student.expected_expire_at.isoformat() if student.expected_expire_at else "",
            }
            for student, binding, account in rows
        ],
        filename_prefix="学生台账",
        columns=["学号", "姓名", "当前账号", "绑定到期", "来源到期", "预期到期"],
    )
    db.session.commit()
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


@bp.get("/students/<student_no>")
@require_session
def student_detail(student_no: str):
    student = Student.query.filter_by(student_no=student_no).first()
    if student is None:
        return error("STU404", "学生不存在", status=404)
    binding = CurrentBinding.query.filter_by(student_id=student.id).first()
    account = db.session.get(MobileAccount, binding.mobile_account_id) if binding else None
    return success(
        {
            "student_no": student.student_no,
            "name": student.name,
            "expected_expire_at": student.expected_expire_at.isoformat() if student.expected_expire_at else None,
            "source_expire_at": student.source_expire_at.isoformat() if student.source_expire_at else None,
            "current_binding": (
                {
                    "mobile_account_id": account.id,
                    "mobile_account": account.account,
                    "expire_at": binding.expire_at.isoformat(),
                }
                if binding and account
                else None
            ),
        }
    )


@bp.get("/students/<student_no>/history")
@require_session
def student_history(student_no: str):
    student = Student.query.filter_by(student_no=student_no).first()
    if student is None:
        return error("STU404", "学生不存在", status=404)

    action_type = request.args.get("action_type")
    sort_by = request.args.get("sort_by", "created_at")
    sort_order = request.args.get("sort_order", "desc")
    page, page_size = _paging_from_request()

    query = _student_history_query(student.id, action_type)
    direction, order_column = _student_history_order(sort_by, sort_order)
    total = query.count()
    rows = (
        query.order_by(direction(order_column), BindingHistory.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return success(
        {
            "items": [
                {
                    "id": row.id,
                    "action_type": row.action_type,
                    "old_mobile_account_id": row.old_mobile_account_id,
                    "new_mobile_account_id": row.new_mobile_account_id,
                    "created_at": row.created_at.isoformat(),
                }
                for row in rows
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@bp.post("/students/<student_no>/history/export")
@require_session
@require_csrf
def export_student_history(student_no: str):
    student = Student.query.filter_by(student_no=student_no).first()
    if student is None:
        return error("STU404", "学生不存在", status=404)

    payload = request.get_json(silent=True) or {}
    action_type = payload.get("action_type")
    sort_by = payload.get("sort_by", "created_at")
    sort_order = payload.get("sort_order", "desc")

    old_account = aliased(MobileAccount)
    new_account = aliased(MobileAccount)
    direction, order_column = _student_history_order(sort_by, sort_order)
    rows = db.session.execute(
        select(BindingHistory, old_account.account, new_account.account)
        .outerjoin(old_account, old_account.id == BindingHistory.old_mobile_account_id)
        .outerjoin(new_account, new_account.id == BindingHistory.new_mobile_account_id)
        .where(BindingHistory.student_id == student.id)
        .where(BindingHistory.action_type == action_type if action_type else True)
        .order_by(direction(order_column), BindingHistory.id.desc())
    ).all()
    if not rows:
        return error("EXP422", "该学生当前筛选条件下没有可导出的历史记录", status=422)

    export_job = create_tabular_export(
        None,
        [
            {
                "学号": student.student_no,
                "姓名": student.name or "",
                "时间": history.created_at.isoformat(sep=" "),
                "动作": ACTION_TYPE_LABELS.get(history.action_type, history.action_type),
                "旧账号ID": history.old_mobile_account_id or "",
                "旧账号": old_account_name or "",
                "新账号ID": history.new_mobile_account_id or "",
                "新账号": new_account_name or "",
            }
            for history, old_account_name, new_account_name in rows
        ],
        filename_prefix="学生台账历史",
        columns=["学号", "姓名", "时间", "动作", "旧账号ID", "旧账号", "新账号ID", "新账号"],
    )
    db.session.commit()
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


@bp.get("/ledger/accounts/<account>")
@require_session
def ledger_account(account: str):
    target = MobileAccount.query.filter_by(account=account).first()
    if target is None:
        return error("ACC404", "账号不存在", status=404)

    action_type = request.args.get("action_type")
    sort_by = request.args.get("sort_by", "created_at")
    sort_order = request.args.get("sort_order", "desc")
    page, page_size = _paging_from_request()

    query = _account_history_query(target.id, action_type)
    direction, order_column = _account_history_order(sort_by, sort_order)
    total = query.count()
    rows = (
        query.order_by(direction(order_column), BindingHistory.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return success(
        {
            "account": target.account,
            "status": target.status,
            "items": [
                {
                    "id": row.id,
                    "student_id": row.student_id,
                    "action_type": row.action_type,
                    "created_at": row.created_at.isoformat(),
                }
                for row in rows
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@bp.post("/ledger/accounts/<account>/export")
@require_session
@require_csrf
def export_account_history(account: str):
    target = MobileAccount.query.filter_by(account=account).first()
    if target is None:
        return error("ACC404", "账号不存在", status=404)

    payload = request.get_json(silent=True) or {}
    action_type = payload.get("action_type")
    sort_by = payload.get("sort_by", "created_at")
    sort_order = payload.get("sort_order", "desc")

    student_alias = aliased(Student)
    old_account = aliased(MobileAccount)
    new_account = aliased(MobileAccount)
    direction, order_column = _account_history_order(sort_by, sort_order)
    rows = db.session.execute(
        select(BindingHistory, student_alias.student_no, student_alias.name, old_account.account, new_account.account)
        .outerjoin(student_alias, student_alias.id == BindingHistory.student_id)
        .outerjoin(old_account, old_account.id == BindingHistory.old_mobile_account_id)
        .outerjoin(new_account, new_account.id == BindingHistory.new_mobile_account_id)
        .where(
            (BindingHistory.old_mobile_account_id == target.id) | (BindingHistory.new_mobile_account_id == target.id)
        )
        .where(BindingHistory.action_type == action_type if action_type else True)
        .order_by(direction(order_column), BindingHistory.id.desc())
    ).all()
    if not rows:
        return error("EXP422", "该账号当前筛选条件下没有可导出的历史记录", status=422)

    export_job = create_tabular_export(
        None,
        [
            {
                "账号": target.account,
                "时间": history.created_at.isoformat(sep=" "),
                "动作": ACTION_TYPE_LABELS.get(history.action_type, history.action_type),
                "学号": student_no or "",
                "姓名": student_name or "",
                "旧账号ID": history.old_mobile_account_id or "",
                "旧账号": old_account_name or "",
                "新账号ID": history.new_mobile_account_id or "",
                "新账号": new_account_name or "",
            }
            for history, student_no, student_name, old_account_name, new_account_name in rows
        ],
        filename_prefix="账号台账历史",
        columns=["账号", "时间", "动作", "学号", "姓名", "旧账号ID", "旧账号", "新账号ID", "新账号"],
    )
    db.session.commit()
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
