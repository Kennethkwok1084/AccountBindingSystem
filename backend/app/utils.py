"""Utility helpers."""

from .models import BindingLog
from . import db
from datetime import datetime


def add_log(
    username: str, student_id: str | None, action: str, operator: str = "system"
) -> None:
    """Insert a binding log entry."""
    log = BindingLog(
        username=username,
        student_id=student_id,
        action=action,
        operator=operator,
        bind_time=datetime.utcnow(),
    )
    db.session.add(log)
    db.session.commit()
