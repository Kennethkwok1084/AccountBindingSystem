from __future__ import annotations

import threading
import uuid
from contextlib import contextmanager
from typing import Any

from flask import has_request_context, request

from ..auth import current_user
from ..extensions import db
from ..models import AuditLog, EntityChangeLog, OperationAuditEvent
from .syslog_service import emit_syslog

_trace_ctx = threading.local()


def _current_trace_id() -> str | None:
    return getattr(_trace_ctx, "trace_id", None)


def _current_source() -> str:
    return getattr(_trace_ctx, "source", "api")


@contextmanager
def operation_trace(event_type: str, source: str = "api"):
    """Set a trace context for an operation so child record calls pick up the same trace_id."""
    trace_id = str(uuid.uuid4())
    prev_trace_id = getattr(_trace_ctx, "trace_id", None)
    prev_source = getattr(_trace_ctx, "source", "api")
    _trace_ctx.trace_id = trace_id
    _trace_ctx.source = source
    try:
        yield trace_id
    finally:
        _trace_ctx.trace_id = prev_trace_id
        _trace_ctx.source = prev_source


def set_trace_context(trace_id: str, source: str = "api") -> None:
    """Set trace context from outside a context manager (e.g. background threads)."""
    _trace_ctx.trace_id = trace_id
    _trace_ctx.source = source


def clear_trace_context() -> None:
    _trace_ctx.trace_id = None
    _trace_ctx.source = "api"


def write_audit(
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    detail: dict | None = None,
    operator_id: int | None = None,
) -> None:
    resolved_operator_id = operator_id
    if resolved_operator_id is None and has_request_context():
        user = current_user()
        resolved_operator_id = user.id if user else None
    log = AuditLog(
        operator_id=resolved_operator_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        detail_json=detail or {},
    )
    db.session.add(log)
    db.session.flush()
    emit_syslog(
        "audit_log",
        {
            "audit_id": log.id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "operator_id": resolved_operator_id,
            "detail": detail or {},
        },
    )


def record_operation_event(
    event_type: str,
    event_stage: str,
    *,
    source: str | None = None,
    trace_id: str | None = None,
    parent_trace_id: str | None = None,
    operation_batch_id: int | None = None,
    import_job_id: int | None = None,
    student_id: int | None = None,
    student_no: str | None = None,
    mobile_account_id: int | None = None,
    mobile_account: str | None = None,
    operator_id: int | None = None,
    idempotency_key: str | None = None,
    payload: dict | None = None,
    decision: dict | None = None,
) -> OperationAuditEvent:
    resolved_trace_id = trace_id or _current_trace_id() or str(uuid.uuid4())
    resolved_source = source or _current_source()

    resolved_operator_id = operator_id
    if resolved_operator_id is None and has_request_context():
        user = current_user()
        resolved_operator_id = user.id if user else None

    resolved_request_id: str | None = None
    if has_request_context():
        resolved_request_id = request.headers.get("X-Request-ID")

    event = OperationAuditEvent(
        trace_id=resolved_trace_id,
        parent_trace_id=parent_trace_id,
        event_type=event_type,
        event_stage=event_stage,
        source=resolved_source,
        operation_batch_id=operation_batch_id,
        import_job_id=import_job_id,
        student_id=student_id,
        student_no=student_no,
        mobile_account_id=mobile_account_id,
        mobile_account=mobile_account,
        operator_id=resolved_operator_id,
        idempotency_key=idempotency_key,
        request_id=resolved_request_id,
        payload_json=payload or {},
        decision_json=decision or {},
    )
    db.session.add(event)
    db.session.flush()
    return event


def record_entity_change(
    entity_type: str,
    entity_id: Any,
    change_type: str,
    *,
    before: dict | None = None,
    after: dict | None = None,
    reason: str | None = None,
    operation_batch_id: int | None = None,
    student_id: int | None = None,
    mobile_account_id: int | None = None,
) -> None:
    log = EntityChangeLog(
        trace_id=_current_trace_id(),
        entity_type=entity_type,
        entity_id=str(entity_id),
        change_type=change_type,
        before_json=before,
        after_json=after,
        change_reason=reason,
        operation_batch_id=operation_batch_id,
        student_id=student_id,
        mobile_account_id=mobile_account_id,
    )
    db.session.add(log)
    db.session.flush()


def _binding_snapshot(binding) -> dict:
    return {
        "id": binding.id,
        "student_id": binding.student_id,
        "mobile_account_id": binding.mobile_account_id,
        "bind_source": binding.bind_source,
        "bind_type": binding.bind_type,
        "expire_at": binding.expire_at.isoformat() if binding.expire_at else None,
    }


def _account_snapshot(account) -> dict:
    return {
        "id": account.id,
        "account": account.account,
        "status": account.status,
        "batch_id": account.batch_id,
        "disabled_reason": account.disabled_reason,
    }
