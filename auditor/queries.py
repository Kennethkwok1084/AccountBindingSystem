"""Read-only queries against the business database for audit purposes."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _rows(result) -> list[dict]:
    """Convert SQLAlchemy 2 Row objects to plain dicts via _mapping."""
    return [dict(r._mapping) for r in result]


_DEFAULT_ACTION_TYPES = (
    "allocate",
    "manual_fix",
    "rebind",
    "release",
    "renew",
    "sync_bind",
    "sync_expire_at",
    "sync_rebind",
)


def _business_day_start_utc(target_date: date, business_tz: str) -> datetime:
    tz = ZoneInfo(business_tz)
    local_start = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=tz)
    return local_start.astimezone(timezone.utc).replace(tzinfo=None)


def _utc_naive_to_business_day(ts: datetime, business_tz: str) -> date:
    tz = ZoneInfo(business_tz)
    return ts.replace(tzinfo=timezone.utc).astimezone(tz).date()


def _get_binding_history_daily_counts(
    engine: Engine,
    *,
    start_date: date,
    days: int,
    business_tz: str,
) -> list[dict]:
    window_start = _business_day_start_utc(start_date, business_tz)
    window_end = _business_day_start_utc(start_date + timedelta(days=days), business_tz)
    sql = text("""
        SELECT created_at, action_type
        FROM binding_history
        WHERE created_at >= :start AND created_at < :end
        ORDER BY created_at ASC
    """)
    with engine.connect() as conn:
        raw_rows = list(conn.execute(sql, {"start": window_start, "end": window_end}))

    action_types = set(_DEFAULT_ACTION_TYPES)
    counts: dict[tuple[date, str], int] = {}
    for offset in range(days):
        current_day = start_date + timedelta(days=offset)
        for action_type in action_types:
            counts[(current_day, action_type)] = 0

    for row in raw_rows:
        created_at = row._mapping["created_at"]
        action_type = str(row._mapping["action_type"])
        business_day = _utc_naive_to_business_day(created_at, business_tz)
        if action_type not in action_types:
            action_types.add(action_type)
            for offset in range(days):
                current_day = start_date + timedelta(days=offset)
                counts[(current_day, action_type)] = 0
        counts[(business_day, action_type)] = counts.get((business_day, action_type), 0) + 1

    rows: list[dict] = []
    for offset in range(days):
        current_day = start_date + timedelta(days=offset)
        for action_type in sorted(action_types):
            rows.append(
                {
                    "day": current_day,
                    "action_type": action_type,
                    "cnt": counts.get((current_day, action_type), 0),
                }
            )
    return rows


def get_events_in_window(engine: Engine, start: datetime, end: datetime) -> list[dict]:
    sql = text("""
        SELECT id, trace_id, parent_trace_id, event_type, event_stage, source,
               operation_batch_id, import_job_id, student_id, student_no,
               mobile_account_id, mobile_account, operator_id, idempotency_key,
               payload_json, decision_json, created_at
        FROM operation_audit_event
        WHERE created_at >= :start AND created_at < :end
        ORDER BY created_at
    """)
    with engine.connect() as conn:
        return _rows(conn.execute(sql, {"start": start, "end": end}))


def get_entity_changes_in_window(engine: Engine, start: datetime, end: datetime) -> list[dict]:
    sql = text("""
        SELECT id, trace_id, entity_type, entity_id, change_type,
               before_json, after_json, change_reason,
               operation_batch_id, student_id, mobile_account_id, created_at
        FROM entity_change_log
        WHERE created_at >= :start AND created_at < :end
        ORDER BY created_at
    """)
    with engine.connect() as conn:
        return _rows(conn.execute(sql, {"start": start, "end": end}))


def get_scheduler_runs_in_window(engine: Engine, start: datetime, end: datetime) -> list[dict]:
    sql = text("""
        SELECT id, job_name, status, message, started_at, finished_at
        FROM scheduler_run_log
        WHERE started_at >= :start AND started_at < :end
        ORDER BY started_at
    """)
    with engine.connect() as conn:
        return _rows(conn.execute(sql, {"start": start, "end": end}))


def check_duplicate_student_bindings(engine: Engine) -> list[dict]:
    """HARD: student_id must be unique in current_binding."""
    sql = text("""
        SELECT student_id, COUNT(*) as cnt
        FROM current_binding
        GROUP BY student_id
        HAVING COUNT(*) > 1
    """)
    with engine.connect() as conn:
        return _rows(conn.execute(sql))


def check_duplicate_account_bindings(engine: Engine) -> list[dict]:
    """HARD: mobile_account_id must be unique in current_binding."""
    sql = text("""
        SELECT mobile_account_id, COUNT(*) as cnt
        FROM current_binding
        GROUP BY mobile_account_id
        HAVING COUNT(*) > 1
    """)
    with engine.connect() as conn:
        return _rows(conn.execute(sql))


def check_binding_account_status_mismatch(engine: Engine) -> list[dict]:
    """HARD: accounts linked in current_binding must be 'assigned'."""
    sql = text("""
        SELECT cb.id AS binding_id, cb.student_id, cb.mobile_account_id,
               ma.account, ma.status AS account_status
        FROM current_binding cb
        JOIN mobile_account ma ON ma.id = cb.mobile_account_id
        WHERE ma.status != 'assigned'
    """)
    with engine.connect() as conn:
        return _rows(conn.execute(sql))


def check_expired_bindings_not_released(engine: Engine, business_date: date) -> list[dict]:
    """HARD: no current_binding should have expire_at < today."""
    sql = text("""
        SELECT cb.id, cb.student_id, cb.mobile_account_id, cb.expire_at
        FROM current_binding cb
        WHERE cb.expire_at < :business_date
    """)
    with engine.connect() as conn:
        return _rows(conn.execute(sql, {"business_date": business_date}))


def check_orphan_assigned_accounts(engine: Engine) -> list[dict]:
    """HARD: mobile_account with status='assigned' must have a current_binding row."""
    sql = text("""
        SELECT ma.id, ma.account, ma.status
        FROM mobile_account ma
        LEFT JOIN current_binding cb ON cb.mobile_account_id = ma.id
        WHERE ma.status = 'assigned' AND cb.id IS NULL
    """)
    with engine.connect() as conn:
        return _rows(conn.execute(sql))


def check_binding_expire_release_ran(
    engine: Engine, window_start: datetime, window_end: datetime
) -> list[dict]:
    """HARD: binding_expire_release must have succeeded in the audit window (UTC range)."""
    sql = text("""
        SELECT id, job_name, status, message, started_at
        FROM scheduler_run_log
        WHERE job_name = 'binding_expire_release'
          AND started_at >= :window_start
          AND started_at < :window_end
          AND status = 'success'
        ORDER BY started_at DESC
        LIMIT 1
    """)
    with engine.connect() as conn:
        return _rows(conn.execute(sql, {"window_start": window_start, "window_end": window_end}))


def get_daily_action_counts(engine: Engine, start: datetime, end: datetime) -> dict[str, Any]:
    """Counts of key actions in the audit window."""
    sql = text("""
        SELECT
            SUM(CASE WHEN action_type = 'release' THEN 1 ELSE 0 END) AS release_count,
            SUM(CASE WHEN action_type = 'rebind' THEN 1 ELSE 0 END) AS rebind_count,
            SUM(CASE WHEN action_type = 'allocate' THEN 1 ELSE 0 END) AS allocate_count,
            SUM(CASE WHEN action_type = 'manual_fix' THEN 1 ELSE 0 END) AS manual_fix_count
        FROM binding_history
        WHERE created_at >= :start AND created_at < :end
    """)
    with engine.connect() as conn:
        row = conn.execute(sql, {"start": start, "end": end}).one()
        return dict(row._mapping)


def get_7day_baseline(engine: Engine, audit_date: date, business_tz: str) -> list[dict]:
    """Daily binding action counts for the 7 business days before audit_date."""
    start_date = audit_date - timedelta(days=7)
    return _get_binding_history_daily_counts(
        engine,
        start_date=start_date,
        days=7,
        business_tz=business_tz,
    )


def get_open_alerts(engine: Engine) -> list[dict]:
    sql = text("""
        SELECT id, type, level, title, content, created_at
        FROM alert_record
        WHERE is_resolved = FALSE
        ORDER BY created_at DESC
        LIMIT 20
    """)
    with engine.connect() as conn:
        return _rows(conn.execute(sql))


def get_preview_execute_pairs(engine: Engine, start: datetime, end: datetime) -> list[dict]:
    """Return preview+execute events for charge and full-list ops."""
    sql = text("""
        SELECT event_type, event_stage, operation_batch_id, import_job_id,
               decision_json, created_at
        FROM operation_audit_event
        WHERE event_type IN ('charge_preview','charge_execute','full_list_preview','full_list_execute')
          AND created_at >= :start AND created_at < :end
        ORDER BY created_at
    """)
    with engine.connect() as conn:
        return _rows(conn.execute(sql, {"start": start, "end": end}))


def get_current_inventory(engine: Engine) -> dict[str, int]:
    sql = text("""
        SELECT status, COUNT(*) AS cnt
        FROM mobile_account
        GROUP BY status
    """)
    with engine.connect() as conn:
        return {str(r._mapping["status"]): int(r._mapping["cnt"]) for r in conn.execute(sql)}


def get_30day_baseline(engine: Engine, audit_date: date, business_tz: str) -> list[dict]:
    """Per-day action counts over the 30 business days before audit_date."""
    start_date = audit_date - timedelta(days=30)
    return _get_binding_history_daily_counts(
        engine,
        start_date=start_date,
        days=30,
        business_tz=business_tz,
    )


def get_audit_history(engine: Engine, days: int = 30) -> list[dict]:
    """Return the last N daily_audit_run rows, most recent first.
    risk_score/risk_level extracted from summary_json (no extra columns needed)."""
    sql = text("""
        SELECT id, audit_date, overall_status, hard_failures, warnings,
               (summary_json->>'risk_score')::int AS risk_score,
               summary_json->>'risk_level' AS risk_level,
               created_at
        FROM daily_audit_run
        ORDER BY audit_date DESC
        LIMIT :limit
    """)
    with engine.connect() as conn:
        return _rows(conn.execute(sql, {"limit": days}))
