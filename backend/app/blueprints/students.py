from __future__ import annotations

from flask import Blueprint
from sqlalchemy import asc, desc, func, or_, select

from ..extensions import db
from ..models import BindingHistory, CurrentBinding, MobileAccount, Student
from ..responses import error, success
from ..security import require_session


bp = Blueprint("students", __name__)


def _bool_arg(value: str | None):
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
    from flask import request

    student = Student.query.filter_by(student_no=student_no).first()
    if student is None:
        return error("STU404", "学生不存在", status=404)

    action_type = request.args.get("action_type")
    sort_by = request.args.get("sort_by", "created_at")
    sort_order = request.args.get("sort_order", "desc")
    page, page_size = _paging_from_request()

    query = BindingHistory.query.filter_by(student_id=student.id)
    if action_type:
        query = query.filter(BindingHistory.action_type == action_type)

    sortable_columns = {
        "id": BindingHistory.id,
        "created_at": BindingHistory.created_at,
        "action_type": BindingHistory.action_type,
        "old_mobile_account_id": BindingHistory.old_mobile_account_id,
        "new_mobile_account_id": BindingHistory.new_mobile_account_id,
    }
    order_column = sortable_columns.get(sort_by, BindingHistory.created_at)
    direction = _sort_direction(sort_order)
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


@bp.get("/ledger/accounts/<account>")
@require_session
def ledger_account(account: str):
    from flask import request

    target = MobileAccount.query.filter_by(account=account).first()
    if target is None:
        return error("ACC404", "账号不存在", status=404)

    action_type = request.args.get("action_type")
    sort_by = request.args.get("sort_by", "created_at")
    sort_order = request.args.get("sort_order", "desc")
    page, page_size = _paging_from_request()

    query = BindingHistory.query.filter(
        (BindingHistory.old_mobile_account_id == target.id) | (BindingHistory.new_mobile_account_id == target.id)
    )
    if action_type:
        query = query.filter(BindingHistory.action_type == action_type)

    sortable_columns = {
        "id": BindingHistory.id,
        "created_at": BindingHistory.created_at,
        "action_type": BindingHistory.action_type,
        "student_id": BindingHistory.student_id,
    }
    order_column = sortable_columns.get(sort_by, BindingHistory.created_at)
    direction = _sort_direction(sort_order)
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
