from __future__ import annotations

from ..auth import current_user
from ..extensions import db
from ..models import AuditLog


def write_audit(action: str, resource_type: str, resource_id: str | None = None, detail: dict | None = None) -> None:
    user = current_user()
    log = AuditLog(
        operator_id=user.id if user else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        detail_json=detail or {},
    )
    db.session.add(log)
    db.session.flush()

