from __future__ import annotations

from flask import Blueprint

from ..extensions import db
from ..models import BindingHistory, CurrentBinding, MobileAccount, Student
from ..responses import error, success
from ..security import require_session


bp = Blueprint("students", __name__)


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
    rows = BindingHistory.query.filter_by(student_id=student.id).order_by(BindingHistory.id.desc()).all()
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
            "total": len(rows),
        }
    )


@bp.get("/ledger/accounts/<account>")
@require_session
def ledger_account(account: str):
    target = MobileAccount.query.filter_by(account=account).first()
    if target is None:
        return error("ACC404", "账号不存在", status=404)
    rows = BindingHistory.query.filter(
        (BindingHistory.old_mobile_account_id == target.id) | (BindingHistory.new_mobile_account_id == target.id)
    ).order_by(BindingHistory.id.desc()).all()
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
            "total": len(rows),
        }
    )
