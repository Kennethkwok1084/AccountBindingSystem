"""Second-layer LLM report generation.

Reads only first-layer audit results plus summarized evidence and calls the
SiliconFlow OpenAI-compatible chat completions endpoint. This layer never
touches the business database directly.
"""
from __future__ import annotations

import json
import os
from datetime import date

import httpx


_CLIENT: httpx.Client | None = None


def _client() -> httpx.Client:
    global _CLIENT
    if _CLIENT is None:
        timeout_seconds = int(os.environ.get("AUDIT_LLM_TIMEOUT_SECONDS", "1800"))
        _CLIENT = httpx.Client(
            base_url=os.environ.get("AUDIT_LLM_BASE_URL", "https://api.siliconflow.cn/v1"),
            # Kimi report generation can legitimately take minutes on larger payloads.
            timeout=httpx.Timeout(timeout_seconds),
        )
    return _CLIENT


_SYSTEM_PROMPT = """\
你是一个移动账号绑定系统的运维审计助手。你的职责是基于第一层规则引擎的结果，为运维人员生成清晰的中文日报。

约束：
- 你只能基于提供的 JSON 数据进行分析，不能假设或捏造数据库中未体现的信息
- 你不能建议直接修改数据库
- 你的结论必须有证据支持，不能做无依据的推断
- 输出格式为 Markdown
- 风险等级：low=低风险 medium=中等风险 high=高风险 critical=严重风险
"""

_REPORT_TEMPLATE = """\
请根据以下今日审计数据，生成运维日报。

**审计日期**：{audit_date}
**整体状态**：{overall_status}（FAIL=硬失败/WARN=需关注/PASS=正常）
**风险评分**：{risk_score}/100（{risk_level}）
**硬失败数**：{hard_failures}  **警告数**：{warnings}

**业务指标（今日）**：
```json
{metrics_json}
```

**发现的问题（第一层规则审计）**：
```json
{issues_json}
```

**历史趋势（近7/30天）**：
```json
{trend_json}
```

**近期事件摘要（今日）**：
```json
{events_sample_json}
```

**当前未解决告警**：
```json
{open_alerts_json}
```

请输出以下内容（Markdown 格式）：

## 今日总体判断
一句话：正常 / 需关注 / 高风险，及简要理由。

## Top 风险项
按严重程度排序，每项包含：规则编号、描述、可能原因。

## 趋势分析
结合近7/30天数据，说明当前风险是偶发还是持续恶化。

## 建议人工复核
列出需要人工核查的具体对象（批次、学生编号、账号、调度任务）。

## 简明推送摘要
不超过3句话，适合发送到即时通讯工具。
"""


def generate_report(
    audit_date: date,
    summary: dict,
    events_sample: list[dict],
    open_alerts: list[dict],
    trend: dict | None = None,
) -> tuple[str, str]:
    """Returns (report_markdown, llm_status)."""
    api_key = os.environ.get("SILICONFLOW_API_KEY", "").strip()
    if not api_key or api_key in {"YOUR_API_KEY", "占位符"}:
        return "", "skipped_no_api_key"

    try:
        risk_level_cn = {
            "low": "低风险", "medium": "中等风险",
            "high": "高风险", "critical": "严重风险",
        }.get(str(summary.get("risk_level", "")), str(summary.get("risk_level", "未知")))

        prompt = _REPORT_TEMPLATE.format(
            audit_date=audit_date.isoformat(),
            overall_status=summary.get("overall_status", "UNKNOWN"),
            risk_score=summary.get("risk_score", "N/A"),
            risk_level=risk_level_cn,
            hard_failures=summary.get("hard_failures", 0),
            warnings=summary.get("warnings", 0),
            metrics_json=json.dumps(summary.get("metrics", {}), ensure_ascii=False, indent=2),
            issues_json=json.dumps(summary.get("issues", []), ensure_ascii=False, indent=2, default=str),
            trend_json=json.dumps(trend or {}, ensure_ascii=False, indent=2, default=str),
            events_sample_json=json.dumps(
                _sanitize_events(events_sample[:20]), ensure_ascii=False, indent=2, default=str
            ),
            open_alerts_json=json.dumps(open_alerts[:10], ensure_ascii=False, indent=2, default=str),
        )

        response = _client().post(
            "/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": os.environ.get("AUDIT_LLM_MODEL", "Pro/moonshotai/Kimi-K2.6"),
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "temperature": float(os.environ.get("AUDIT_LLM_TEMPERATURE", "0.2")),
                "max_tokens": int(os.environ.get("AUDIT_LLM_MAX_TOKENS", "2048")),
            },
        )
        response.raise_for_status()
        payload = response.json()
        report_md = (
            payload.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        if not report_md:
            raise ValueError(f"empty response payload: {payload}")
        return report_md, "success"
    except Exception as exc:  # noqa: BLE001
        return f"LLM 报告生成失败: {exc}", "failed"


def _sanitize_events(events: list[dict]) -> list[dict]:
    """Strip payload details; keep only summary fields for LLM context."""
    return [
        {
            "event_type": e.get("event_type"),
            "event_stage": e.get("event_stage"),
            "source": e.get("source"),
            "decision": e.get("decision_json") or {},
            "created_at": str(e.get("created_at", "")),
        }
        for e in events
    ]
