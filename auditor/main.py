"""Auditor main entry point. Runs once per day via cron or on-demand."""
from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import create_engine, text

from llm_reporter import generate_report
from queries import (
    get_current_inventory,
    get_daily_action_counts,
    get_events_in_window,
    get_open_alerts,
)
from rules import AuditIssue, build_summary, get_trend_summary, run_all_checks


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _get_audit_timezone_name() -> str:
    return os.environ.get("AUDIT_TZ", "Asia/Shanghai")


def _get_audit_timezone() -> ZoneInfo:
    return ZoneInfo(_get_audit_timezone_name())


def _get_audit_window(audit_date: date) -> tuple[datetime, datetime]:
    """UTC-naive window covering a full business-timezone calendar day."""
    tz = _get_audit_timezone()
    local_start = datetime(audit_date.year, audit_date.month, audit_date.day, 0, 0, 0, tzinfo=tz)
    local_end = local_start + timedelta(days=1)
    start_utc = local_start.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = local_end.astimezone(timezone.utc).replace(tzinfo=None)
    return start_utc, end_utc


def _today_in_business_tz() -> date:
    return datetime.now(_get_audit_timezone()).date()


def _save_audit_run(
    engine,
    audit_date: date,
    scope_start: datetime,
    scope_end: datetime,
    summary: dict,
    report_md: str,
    llm_status: str,
    issues: list[AuditIssue],
) -> int:
    now = _utcnow()
    with engine.begin() as conn:
        existing = conn.execute(
            text("SELECT id FROM daily_audit_run WHERE audit_date = :d"), {"d": audit_date}
        ).one_or_none()

        if existing:
            run_id = existing[0]
            conn.execute(text("""
                UPDATE daily_audit_run
                SET scope_start_at=:ss, scope_end_at=:se, overall_status=:os,
                    hard_failures=:hf, warnings=:w, llm_status=:ls,
                    summary_json=:sj, report_markdown=:rm
                WHERE id=:id
            """), {
                "ss": scope_start, "se": scope_end,
                "os": summary["overall_status"],
                "hf": summary["hard_failures"], "w": summary["warnings"],
                "ls": llm_status, "sj": json.dumps(summary, default=str),
                "rm": report_md, "id": run_id,
            })
            conn.execute(text("DELETE FROM daily_audit_issue WHERE audit_run_id=:id"), {"id": run_id})
        else:
            row = conn.execute(text("""
                INSERT INTO daily_audit_run
                    (audit_date, scope_start_at, scope_end_at, overall_status,
                     hard_failures, warnings, llm_status, summary_json, report_markdown, created_at)
                VALUES (:ad, :ss, :se, :os, :hf, :w, :ls, :sj, :rm, :ca)
                RETURNING id
            """), {
                "ad": audit_date, "ss": scope_start, "se": scope_end,
                "os": summary["overall_status"],
                "hf": summary["hard_failures"], "w": summary["warnings"],
                "ls": llm_status, "sj": json.dumps(summary, default=str),
                "rm": report_md, "ca": now,
            })
            run_id = row.one()[0]

        for issue in issues:
            conn.execute(text("""
                INSERT INTO daily_audit_issue
                    (audit_run_id, severity, rule_code, title, detail_json, sample_refs_json, created_at)
                VALUES (:rid, :sev, :rc, :title, :dj, :srj, :ca)
            """), {
                "rid": run_id, "sev": issue.severity, "rc": issue.rule_code,
                "title": issue.title,
                "dj": json.dumps(issue.detail, default=str),
                "srj": json.dumps(issue.samples, default=str),
                "ca": now,
            })
    return run_id


def _send_webhook_notification(summary: dict, report_md: str) -> None:
    webhook_url = os.environ.get("AUDIT_REPORT_WEBHOOK")
    if not webhook_url:
        return
    status_emoji = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(summary["overall_status"], "❓")
    risk_label = {"low": "低", "medium": "中", "high": "高", "critical": "严重"}.get(
        summary.get("risk_level", ""), ""
    )
    text_body = (
        f"{status_emoji} 账号绑定系统审计日报\n"
        f"状态：{summary['overall_status']}  风险：{risk_label}（{summary.get('risk_score', '?')}分）\n"
        f"硬失败：{summary['hard_failures']}  警告：{summary['warnings']}\n\n"
        + (report_md[:800] if report_md else "（LLM 报告未生成）")
    )
    try:
        httpx.post(webhook_url, json={"text": text_body}, timeout=10)
    except Exception:  # noqa: BLE001
        print("[auditor] webhook notification failed", file=sys.stderr)
        traceback.print_exc()


def _write_artifacts(audit_date: date, summary: dict, report_md: str) -> None:
    output_dir = os.environ.get("AUDIT_OUTPUT_DIR", "/app/audit_output")
    os.makedirs(output_dir, exist_ok=True)
    date_str = audit_date.isoformat()
    with open(f"{output_dir}/audit_result_{date_str}.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
    if report_md:
        with open(f"{output_dir}/audit_report_{date_str}.md", "w", encoding="utf-8") as f:
            f.write(report_md)


def run_audit(audit_date: date | None = None) -> dict:
    if audit_date is None:
        audit_date = _today_in_business_tz()

    db_url = os.environ.get("AUDIT_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError("AUDIT_DATABASE_URL is required")

    engine = create_engine(db_url, pool_pre_ping=True)

    scope_start, scope_end = _get_audit_window(audit_date)
    business_tz = _get_audit_timezone_name()
    print(
        f"[auditor] running audit for {audit_date}, "
        f"UTC window {scope_start.isoformat()} – {scope_end.isoformat()} "
        f"(business_tz={business_tz})"
    )

    today_counts = get_daily_action_counts(engine, scope_start, scope_end)
    inventory = get_current_inventory(engine)
    trend = get_trend_summary(engine, audit_date, business_tz)

    issues = run_all_checks(engine, audit_date, scope_start, scope_end, today_counts, business_tz)
    summary = build_summary(issues, today_counts, inventory, trend)
    summary["audit_date"] = audit_date.isoformat()

    events = get_events_in_window(engine, scope_start, scope_end)
    open_alerts = get_open_alerts(engine)

    report_md, llm_status = generate_report(audit_date, summary, events, open_alerts, trend)

    run_id = _save_audit_run(engine, audit_date, scope_start, scope_end,
                             summary, report_md, llm_status, issues)
    print(f"[auditor] saved daily_audit_run id={run_id}, status={summary['overall_status']}, "
          f"risk={summary.get('risk_level')}({summary.get('risk_score')})")

    _write_artifacts(audit_date, summary, report_md)
    _send_webhook_notification(summary, report_md)

    engine.dispose()
    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Audit date YYYY-MM-DD (default: today)")
    args = parser.parse_args()

    target_date = date.fromisoformat(args.date) if args.date else _today_in_business_tz()
    result = run_audit(target_date)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    sys.exit(0 if result["overall_status"] != "FAIL" else 1)
