"""First-layer deterministic rule checks. Each check returns a list of AuditIssue."""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy.engine import Engine

from queries import (
    check_binding_account_status_mismatch,
    check_binding_expire_release_ran,
    check_duplicate_account_bindings,
    check_duplicate_student_bindings,
    check_expired_bindings_not_released,
    check_orphan_assigned_accounts,
    get_7day_baseline,
    get_30day_baseline,
    get_audit_history,
    get_open_alerts,
    get_preview_execute_pairs,
    get_scheduler_runs_in_window,
)


@dataclass
class AuditIssue:
    severity: str  # "FAIL" | "WARN"
    rule_code: str
    title: str
    detail: dict = field(default_factory=dict)
    samples: list[dict] = field(default_factory=list)


def run_all_checks(
    engine: Engine,
    audit_date: date,
    window_start: datetime,
    window_end: datetime,
    today_counts: dict[str, Any],
    business_tz: str,
) -> list[AuditIssue]:
    issues: list[AuditIssue] = []
    issues.extend(_check_hard_rules(engine, audit_date, window_start, window_end))
    issues.extend(_check_soft_rules(engine, audit_date, window_start, window_end, today_counts, business_tz))
    issues.extend(_check_trend_rules(engine, audit_date, today_counts, business_tz))
    return issues


def _check_hard_rules(
    engine: Engine, audit_date: date, window_start: datetime, window_end: datetime
) -> list[AuditIssue]:
    issues: list[AuditIssue] = []

    # H001: duplicate student in current_binding
    rows = check_duplicate_student_bindings(engine)
    if rows:
        issues.append(AuditIssue(
            severity="FAIL", rule_code="H001",
            title="current_binding 中存在重复的 student_id",
            detail={"count": len(rows)},
            samples=rows[:5],
        ))

    # H002: duplicate account in current_binding
    rows = check_duplicate_account_bindings(engine)
    if rows:
        issues.append(AuditIssue(
            severity="FAIL", rule_code="H002",
            title="current_binding 中存在重复的 mobile_account_id",
            detail={"count": len(rows)},
            samples=rows[:5],
        ))

    # H003: bound account not in 'assigned' status
    rows = check_binding_account_status_mismatch(engine)
    if rows:
        issues.append(AuditIssue(
            severity="FAIL", rule_code="H003",
            title="current_binding 关联账号状态不是 assigned",
            detail={"count": len(rows)},
            samples=rows[:5],
        ))

    # H004: expired bindings still exist
    rows = check_expired_bindings_not_released(engine, audit_date)
    if rows:
        issues.append(AuditIssue(
            severity="FAIL", rule_code="H004",
            title="存在已过期但未释放的 current_binding",
            detail={"count": len(rows)},
            samples=rows[:5],
        ))

    # H005: assigned accounts with no binding row
    rows = check_orphan_assigned_accounts(engine)
    if rows:
        issues.append(AuditIssue(
            severity="FAIL", rule_code="H005",
            title="mobile_account 状态为 assigned 但无 current_binding 关联",
            detail={"count": len(rows)},
            samples=rows[:5],
        ))

    # H006: binding_expire_release must have succeeded within the audit window (UTC range)
    rows = check_binding_expire_release_ran(engine, window_start, window_end)
    if not rows:
        issues.append(AuditIssue(
            severity="FAIL", rule_code="H006",
            title="binding_expire_release 今日未成功执行",
            detail={
                "audit_date": audit_date.isoformat(),
                "window_utc": f"{window_start.isoformat()} – {window_end.isoformat()}",
            },
        ))

    return issues


def _check_soft_rules(
    engine: Engine,
    audit_date: date,
    window_start: datetime,
    window_end: datetime,
    today_counts: dict[str, Any],
    business_tz: str,
) -> list[AuditIssue]:
    issues: list[AuditIssue] = []

    # S001: rebind/release count significantly above 7-day average
    baseline_rows = get_7day_baseline(engine, audit_date, business_tz)
    if baseline_rows:
        by_action: dict[str, list[int]] = {}
        for row in baseline_rows:
            by_action.setdefault(str(row["action_type"]), []).append(int(row["cnt"]))

        for action in ("rebind", "release"):
            today_val = int(today_counts.get(f"{action}_count") or 0)
            hist = by_action.get(action, [])
            if len(hist) >= 3:
                avg = statistics.mean(hist)
                if avg > 0 and today_val > avg * 3:
                    issues.append(AuditIssue(
                        severity="WARN", rule_code="S001",
                        title=f"今日 {action} 数量显著高于近7天均值",
                        detail={"today": today_val, "7day_avg": round(avg, 1), "ratio": round(today_val / avg, 1)},
                    ))

    # S002: preview conflict count vs execute conflict count divergence
    pairs = get_preview_execute_pairs(engine, window_start, window_end)
    preview_conflicts: list[int] = []
    execute_conflicts: list[int] = []
    for p in pairs:
        d = p.get("decision_json") or {}
        if p["event_stage"] == "preview" and "conflict_count" in d:
            preview_conflicts.append(int(d["conflict_count"]))
        elif p["event_stage"] == "execute" and "conflict_rows" in d:
            execute_conflicts.append(int(d["conflict_rows"]))

    total_preview = sum(preview_conflicts)
    total_execute = sum(execute_conflicts)
    if total_preview < total_execute and (total_execute - total_preview) > 2:
        issues.append(AuditIssue(
            severity="WARN", rule_code="S002",
            title="执行时冲突数明显高于预览时冲突数",
            detail={"preview_conflicts": total_preview, "execute_conflicts": total_execute},
        ))

    # S003: persistent low inventory alert
    open_alerts = get_open_alerts(engine)
    low_stock = [a for a in open_alerts if a["type"] == "inventory_low"]
    if low_stock:
        since = low_stock[0]["created_at"]
        issues.append(AuditIssue(
            severity="WARN", rule_code="S003",
            title="移动账号库存低告警持续存在",
            detail={"open_since": since.isoformat() if isinstance(since, datetime) else str(since)},
        ))

    # S004: repeated failed scheduler runs today
    runs = get_scheduler_runs_in_window(engine, window_start, window_end)
    failed_jobs: dict[str, int] = {}
    for r in runs:
        if r["status"] != "success":
            failed_jobs[str(r["job_name"])] = failed_jobs.get(str(r["job_name"]), 0) + 1
    for job_name, fail_count in failed_jobs.items():
        if fail_count >= 2:
            issues.append(AuditIssue(
                severity="WARN", rule_code="S004",
                title=f"调度任务 {job_name} 今日多次失败",
                detail={"job_name": job_name, "fail_count": fail_count},
            ))

    return issues


def _check_trend_rules(
    engine: Engine,
    audit_date: date,
    today_counts: dict[str, Any],
    business_tz: str,
) -> list[AuditIssue]:
    """Phase 4: rules that compare today against 7/30-day historical baselines."""
    issues: list[AuditIssue] = []

    history = get_audit_history(engine, days=30)
    if not history:
        return issues

    recent = history[:7]  # last 7 audit runs (may be <7)
    prior = history[7:30]  # runs 8–30 days ago

    # T001: consecutive FAIL days — >=2 consecutive = FAIL (trend escalation)
    consecutive_fails = 0
    for h in history:
        if h["overall_status"] == "FAIL":
            consecutive_fails += 1
        else:
            break
    if consecutive_fails >= 2:
        issues.append(AuditIssue(
            severity="FAIL", rule_code="T001",
            title=f"连续 {consecutive_fails} 天审计结果为 FAIL（趋势持续恶化）",
            detail={"consecutive_fails": consecutive_fails},
        ))

    # T002: 7-day avg failures increasing vs prior period
    if recent and prior:
        recent_avg = statistics.mean(h["hard_failures"] for h in recent)
        prior_avg = statistics.mean(h["hard_failures"] for h in prior)
        if prior_avg > 0 and recent_avg > prior_avg * 1.5:
            issues.append(AuditIssue(
                severity="WARN", rule_code="T002",
                title="近7天硬失败率高于前期均值",
                detail={
                    "recent_7day_avg_failures": round(recent_avg, 2),
                    "prior_avg_failures": round(prior_avg, 2),
                    "ratio": round(recent_avg / prior_avg, 2),
                },
            ))

    # T003: 30-day action count anomaly (today vs 30d avg)
    thirty_day_baseline = get_30day_baseline(engine, audit_date, business_tz)
    if thirty_day_baseline:
        by_action_30: dict[str, list[int]] = {}
        for row in thirty_day_baseline:
            by_action_30.setdefault(str(row["action_type"]), []).append(int(row["cnt"]))

        for action in ("rebind", "release", "allocate"):
            today_val = int(today_counts.get(f"{action}_count") or 0)
            hist = by_action_30.get(action, [])
            if len(hist) >= 10:
                avg = statistics.mean(hist)
                stdev = statistics.stdev(hist) if len(hist) > 1 else 0
                # Flag if today is more than 3 standard deviations above 30-day mean
                if stdev > 0 and today_val > avg + 3 * stdev:
                    issues.append(AuditIssue(
                        severity="WARN", rule_code="T003",
                        title=f"今日 {action} 数量超出近30天3σ上限",
                        detail={
                            "today": today_val,
                            "30day_avg": round(avg, 1),
                            "30day_stdev": round(stdev, 1),
                            "3sigma_limit": round(avg + 3 * stdev, 1),
                        },
                    ))

    return issues


def compute_risk_score(issues: list[AuditIssue]) -> tuple[int, str]:
    """Returns (risk_score 0-100, risk_level)."""
    score = 100
    for issue in issues:
        if issue.rule_code.startswith("H"):  # hard rules hit harder
            score -= 20
        elif issue.rule_code.startswith("T"):
            score -= 15
        else:
            score -= 8

    score = max(0, score)
    if score >= 80:
        level = "low"
    elif score >= 55:
        level = "medium"
    elif score >= 30:
        level = "high"
    else:
        level = "critical"
    return score, level


def get_trend_summary(engine: Engine, audit_date: date, business_tz: str) -> dict[str, Any]:
    """Build a 7/30-day trend summary for inclusion in the audit report."""
    history = get_audit_history(engine, days=30)
    thirty_day = get_30day_baseline(engine, audit_date, business_tz)

    # Status distribution over 30 days
    status_counts: dict[str, int] = {}
    avg_hard_failures_7d = 0.0
    avg_hard_failures_30d = 0.0
    avg_warnings_7d = 0.0
    avg_warnings_30d = 0.0
    trend_direction = "stable"
    prev_scores: list[int] = []

    if history:
        for h in history:
            s = str(h.get("overall_status", "UNKNOWN"))
            status_counts[s] = status_counts.get(s, 0) + 1

        recent7 = history[:7]
        if recent7:
            avg_hard_failures_7d = round(statistics.mean(h["hard_failures"] for h in recent7), 2)
            avg_warnings_7d = round(statistics.mean(h["warnings"] for h in recent7), 2)

        avg_hard_failures_30d = round(statistics.mean(h["hard_failures"] for h in history), 2)
        avg_warnings_30d = round(statistics.mean(h["warnings"] for h in history), 2)

        # Trend direction: compare last 7 days vs prior 7 days
        prior7 = history[7:14]
        if recent7 and prior7:
            recent_fail_avg = statistics.mean(h["hard_failures"] for h in recent7)
            prior_fail_avg = statistics.mean(h["hard_failures"] for h in prior7)
            if recent_fail_avg > prior_fail_avg * 1.2:
                trend_direction = "degrading"
            elif recent_fail_avg < prior_fail_avg * 0.8:
                trend_direction = "improving"

        prev_scores = [int(h.get("risk_score", 100)) for h in history[:7] if h.get("risk_score") is not None]

    # 30-day action totals
    action_totals: dict[str, int] = {}
    if thirty_day:
        for row in thirty_day:
            action = str(row["action_type"])
            action_totals[action] = action_totals.get(action, 0) + int(row["cnt"])

    return {
        "days_with_history": len(history),
        "status_distribution_30d": status_counts,
        "avg_hard_failures_7d": avg_hard_failures_7d,
        "avg_hard_failures_30d": avg_hard_failures_30d,
        "avg_warnings_7d": avg_warnings_7d,
        "avg_warnings_30d": avg_warnings_30d,
        "trend_direction": trend_direction,
        "prev_risk_scores_7d": prev_scores,
        "action_totals_30d": action_totals,
    }


def build_summary(
    issues: list[AuditIssue],
    today_counts: dict[str, Any],
    inventory: dict[str, int],
    trend: dict[str, Any] | None = None,
) -> dict[str, Any]:
    hard_failures = sum(1 for i in issues if i.severity == "FAIL")
    warnings = sum(1 for i in issues if i.severity == "WARN")
    overall = "PASS"
    if hard_failures > 0:
        overall = "FAIL"
    elif warnings > 0:
        overall = "WARN"

    risk_score, risk_level = compute_risk_score(issues)

    return {
        "overall_status": overall,
        "hard_failures": hard_failures,
        "warnings": warnings,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "metrics": {
            "binding_actions": today_counts,
            "inventory": inventory,
        },
        "trend": trend or {},
        "checks": [
            {
                "severity": i.severity,
                "rule_code": i.rule_code,
                "title": i.title,
                "detail": i.detail,
            }
            for i in issues
        ],
        "issues": [
            {
                "severity": i.severity,
                "rule_code": i.rule_code,
                "title": i.title,
                "detail": i.detail,
                "samples": i.samples,
            }
            for i in issues
        ],
    }
