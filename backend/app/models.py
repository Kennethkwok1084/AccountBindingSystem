from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Numeric, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .extensions import db


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )


class AdminUser(TimestampMixin, db.Model):
    __tablename__ = "admin_user"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)


class SystemConfig(db.Model):
    __tablename__ = "system_config"

    config_key: Mapped[str] = mapped_column(primary_key=True)
    config_value: Mapped[dict] = mapped_column(db.JSON, nullable=False, default=dict)
    remark: Mapped[str | None] = mapped_column(nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )


class AccountBatch(TimestampMixin, db.Model):
    __tablename__ = "account_batch"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_code: Mapped[str] = mapped_column(unique=True, nullable=False)
    batch_name: Mapped[str | None] = mapped_column(nullable=True)
    batch_type: Mapped[str] = mapped_column(nullable=False, default="normal")
    priority: Mapped[int] = mapped_column(nullable=False, default=100)
    expire_at: Mapped[date | None] = mapped_column(Date)
    warn_days: Mapped[int] = mapped_column(nullable=False, default=1)
    status: Mapped[str] = mapped_column(nullable=False, default="active")
    remark: Mapped[str | None] = mapped_column(nullable=True)

    mobile_accounts: Mapped[list["MobileAccount"]] = relationship(back_populates="batch")


class MobileAccount(TimestampMixin, db.Model):
    __tablename__ = "mobile_account"

    id: Mapped[int] = mapped_column(primary_key=True)
    account: Mapped[str] = mapped_column(unique=True, nullable=False)
    password: Mapped[str] = mapped_column(nullable=False, default="123123")
    batch_id: Mapped[int] = mapped_column(ForeignKey("account_batch.id"), nullable=False)
    status: Mapped[str] = mapped_column(nullable=False, default="available")
    disabled_reason: Mapped[str | None] = mapped_column(nullable=True)
    last_assigned_at: Mapped[datetime | None] = mapped_column(DateTime)

    batch: Mapped["AccountBatch"] = relationship(back_populates="mobile_accounts")


class Student(TimestampMixin, db.Model):
    __tablename__ = "student"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_no: Mapped[str] = mapped_column(unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(nullable=True)
    current_package_name: Mapped[str | None] = mapped_column(nullable=True)
    current_fee_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    expected_expire_at: Mapped[date | None] = mapped_column(Date)
    source_expire_at: Mapped[date | None] = mapped_column(Date)
    last_charge_time: Mapped[datetime | None] = mapped_column(DateTime)


class CurrentBinding(TimestampMixin, db.Model):
    __tablename__ = "current_binding"
    __table_args__ = (
        UniqueConstraint("student_id", name="uq_current_binding_student"),
        UniqueConstraint("mobile_account_id", name="uq_current_binding_mobile_account"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"), nullable=False)
    mobile_account_id: Mapped[int] = mapped_column(ForeignKey("mobile_account.id"), nullable=False)
    bind_source: Mapped[str] = mapped_column(nullable=False)
    bind_type: Mapped[str] = mapped_column(nullable=False)
    bind_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    expire_at: Mapped[date] = mapped_column(Date, nullable=False)

    student: Mapped["Student"] = relationship()
    mobile_account: Mapped["MobileAccount"] = relationship()


class BindingHistory(db.Model):
    __tablename__ = "binding_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"), nullable=False)
    old_mobile_account_id: Mapped[int | None] = mapped_column(ForeignKey("mobile_account.id"))
    new_mobile_account_id: Mapped[int | None] = mapped_column(ForeignKey("mobile_account.id"))
    action_type: Mapped[str] = mapped_column(nullable=False)
    old_expire_at: Mapped[date | None] = mapped_column(Date)
    new_expire_at: Mapped[date | None] = mapped_column(Date)
    detail_json: Mapped[dict] = mapped_column(db.JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class ImportJob(TimestampMixin, db.Model):
    __tablename__ = "import_job"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_type: Mapped[str] = mapped_column(nullable=False)
    original_filename: Mapped[str] = mapped_column(nullable=False)
    stored_path: Mapped[str] = mapped_column(nullable=False)
    file_checksum: Mapped[str | None] = mapped_column(nullable=True)
    sheet_name: Mapped[str | None] = mapped_column(nullable=True)
    mapping_json: Mapped[dict] = mapped_column(db.JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(nullable=False, default="uploaded")
    total_rows: Mapped[int] = mapped_column(nullable=False, default=0)
    success_rows: Mapped[int] = mapped_column(nullable=False, default=0)
    failed_rows: Mapped[int] = mapped_column(nullable=False, default=0)
    error_summary: Mapped[str | None] = mapped_column(nullable=True)
    operator_id: Mapped[int] = mapped_column(ForeignKey("admin_user.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class ImportJobError(db.Model):
    __tablename__ = "import_job_error"

    id: Mapped[int] = mapped_column(primary_key=True)
    import_job_id: Mapped[int] = mapped_column(ForeignKey("import_job.id"), nullable=False)
    row_no: Mapped[int] = mapped_column(nullable=False)
    field_name: Mapped[str | None] = mapped_column(nullable=True)
    error_code: Mapped[str] = mapped_column(nullable=False)
    error_message: Mapped[str] = mapped_column(nullable=False)
    raw_data: Mapped[dict] = mapped_column(db.JSON, nullable=False, default=dict)


class OperationBatch(TimestampMixin, db.Model):
    __tablename__ = "operation_batch"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_type: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False, default="previewed")
    source_import_job_id: Mapped[int | None] = mapped_column(ForeignKey("import_job.id"))
    idempotency_key: Mapped[str | None] = mapped_column(unique=True)
    last_processed_charge_time_before: Mapped[datetime | None] = mapped_column(DateTime)
    last_processed_charge_time_after: Mapped[datetime | None] = mapped_column(DateTime)
    total_rows: Mapped[int] = mapped_column(nullable=False, default=0)
    success_rows: Mapped[int] = mapped_column(nullable=False, default=0)
    failed_rows: Mapped[int] = mapped_column(nullable=False, default=0)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime)
    operator_id: Mapped[int] = mapped_column(ForeignKey("admin_user.id"), nullable=False)


class OperationBatchDetail(TimestampMixin, db.Model):
    __tablename__ = "operation_batch_detail"

    id: Mapped[int] = mapped_column(primary_key=True)
    operation_batch_id: Mapped[int] = mapped_column(ForeignKey("operation_batch.id"), nullable=False)
    row_no: Mapped[int] = mapped_column(nullable=False)
    student_id: Mapped[int | None] = mapped_column(ForeignKey("student.id"))
    student_no: Mapped[str | None] = mapped_column(nullable=True)
    student_name: Mapped[str | None] = mapped_column(nullable=True)
    action_plan: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False, default="previewed")
    old_mobile_account_id: Mapped[int | None] = mapped_column(ForeignKey("mobile_account.id"))
    new_mobile_account_id: Mapped[int | None] = mapped_column(ForeignKey("mobile_account.id"))
    old_expire_at: Mapped[date | None] = mapped_column(Date)
    new_expire_at: Mapped[date | None] = mapped_column(Date)
    charge_time: Mapped[datetime | None] = mapped_column(DateTime)
    package_name: Mapped[str | None] = mapped_column(nullable=True)
    fee_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    result_message: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict] = mapped_column(db.JSON, nullable=False, default=dict)
    export_included: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ExportJob(db.Model):
    __tablename__ = "export_job"

    id: Mapped[int] = mapped_column(primary_key=True)
    operation_batch_id: Mapped[int | None] = mapped_column(ForeignKey("operation_batch.id"))
    filename: Mapped[str] = mapped_column(nullable=False)
    stored_path: Mapped[str] = mapped_column(nullable=False)
    row_count: Mapped[int] = mapped_column(nullable=False, default=0)
    status: Mapped[str] = mapped_column(nullable=False, default="ready")
    created_by: Mapped[int] = mapped_column(ForeignKey("admin_user.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime)


class AlertRecord(db.Model):
    __tablename__ = "alert_record"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(nullable=False)
    level: Mapped[str] = mapped_column(nullable=False, default="warning")
    title: Mapped[str] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(nullable=False, default="open")
    is_resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resolution_note: Mapped[str | None] = mapped_column(Text)
    related_batch_id: Mapped[int | None] = mapped_column(ForeignKey("account_batch.id"))
    related_student_id: Mapped[int | None] = mapped_column(ForeignKey("student.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)


class AuditLog(db.Model):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("admin_user.id"))
    action: Mapped[str] = mapped_column(nullable=False)
    resource_type: Mapped[str] = mapped_column(nullable=False)
    resource_id: Mapped[str | None] = mapped_column(nullable=True)
    detail_json: Mapped[dict] = mapped_column(db.JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class SchedulerRunLog(db.Model):
    __tablename__ = "scheduler_run_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_name: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class OperationAuditEvent(db.Model):
    """Business-level event evidence for audit replay."""

    __tablename__ = "operation_audit_event"
    __table_args__ = (
        Index("ix_oae_event_type_created", "event_type", "created_at"),
        Index("ix_oae_trace_id", "trace_id"),
        Index("ix_oae_operation_batch_id", "operation_batch_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    trace_id: Mapped[str] = mapped_column(nullable=False)
    parent_trace_id: Mapped[str | None] = mapped_column(nullable=True)
    event_type: Mapped[str] = mapped_column(nullable=False)
    event_stage: Mapped[str] = mapped_column(nullable=False)
    source: Mapped[str] = mapped_column(nullable=False, default="api")
    operation_batch_id: Mapped[int | None] = mapped_column(ForeignKey("operation_batch.id"), nullable=True)
    import_job_id: Mapped[int | None] = mapped_column(ForeignKey("import_job.id"), nullable=True)
    student_id: Mapped[int | None] = mapped_column(ForeignKey("student.id"), nullable=True)
    student_no: Mapped[str | None] = mapped_column(nullable=True)
    mobile_account_id: Mapped[int | None] = mapped_column(ForeignKey("mobile_account.id"), nullable=True)
    mobile_account: Mapped[str | None] = mapped_column(nullable=True)
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("admin_user.id"), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(nullable=True)
    request_id: Mapped[str | None] = mapped_column(nullable=True)
    payload_json: Mapped[dict] = mapped_column(db.JSON, nullable=False, default=dict)
    decision_json: Mapped[dict] = mapped_column(db.JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class EntityChangeLog(db.Model):
    """Before/after state log for key business entity mutations."""

    __tablename__ = "entity_change_log"
    __table_args__ = (
        Index("ix_ecl_trace_id", "trace_id"),
        Index("ix_ecl_entity", "entity_type", "entity_id"),
        Index("ix_ecl_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    trace_id: Mapped[str | None] = mapped_column(nullable=True)
    entity_type: Mapped[str] = mapped_column(nullable=False)
    entity_id: Mapped[str] = mapped_column(nullable=False)
    change_type: Mapped[str] = mapped_column(nullable=False)
    before_json: Mapped[dict | None] = mapped_column(db.JSON, nullable=True)
    after_json: Mapped[dict | None] = mapped_column(db.JSON, nullable=True)
    change_reason: Mapped[str | None] = mapped_column(nullable=True)
    operation_batch_id: Mapped[int | None] = mapped_column(nullable=True)
    student_id: Mapped[int | None] = mapped_column(nullable=True)
    mobile_account_id: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class DailyAuditRun(db.Model):
    """Daily audit execution record."""

    __tablename__ = "daily_audit_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    audit_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    scope_start_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    scope_end_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    overall_status: Mapped[str] = mapped_column(nullable=False, default="UNKNOWN")
    hard_failures: Mapped[int] = mapped_column(nullable=False, default=0)
    warnings: Mapped[int] = mapped_column(nullable=False, default=0)
    llm_status: Mapped[str | None] = mapped_column(nullable=True)
    summary_json: Mapped[dict] = mapped_column(db.JSON, nullable=False, default=dict)
    report_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    issues: Mapped[list["DailyAuditIssue"]] = relationship(back_populates="audit_run")


class DailyAuditIssue(db.Model):
    """Individual issue found during a daily audit run."""

    __tablename__ = "daily_audit_issue"

    id: Mapped[int] = mapped_column(primary_key=True)
    audit_run_id: Mapped[int] = mapped_column(ForeignKey("daily_audit_run.id"), nullable=False)
    severity: Mapped[str] = mapped_column(nullable=False)
    rule_code: Mapped[str] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(nullable=False)
    detail_json: Mapped[dict] = mapped_column(db.JSON, nullable=False, default=dict)
    sample_refs_json: Mapped[dict] = mapped_column(db.JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    audit_run: Mapped["DailyAuditRun"] = relationship(back_populates="issues")


def load_models() -> None:
    return None
