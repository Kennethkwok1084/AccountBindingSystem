from __future__ import annotations

from flask import Blueprint, request

from ..models import SchedulerRunLog
from ..responses import error, success
from ..security import require_csrf, require_session
from ..services.scheduler_service import JOB_RUNNERS


bp = Blueprint("scheduler", __name__)


def _require_idempotency_key():
    token = request.headers.get("X-Idempotency-Key")
    if not token:
        return None, error("SCH400", "缺少 X-Idempotency-Key", status=400)
    return token, None


@bp.get("/scheduler/jobs")
@require_session
def jobs():
    return success({"items": [{"job_name": job_name} for job_name in JOB_RUNNERS]})


@bp.post("/scheduler/run/<job_name>")
@require_session
@require_csrf
def run_job(job_name: str):
    _, failure = _require_idempotency_key()
    if failure is not None:
        return failure
    runner = JOB_RUNNERS.get(job_name)
    if runner is None:
        return error("SCH404", "任务不存在", status=404)
    message = runner()
    return success({"job_name": job_name, "message": message})


@bp.get("/scheduler/runs")
@require_session
def scheduler_runs():
    items = SchedulerRunLog.query.order_by(SchedulerRunLog.id.desc()).all()
    return success(
        {
            "items": [
                {
                    "id": item.id,
                    "job_name": item.job_name,
                    "status": item.status,
                    "message": item.message,
                    "started_at": item.started_at.isoformat(),
                    "finished_at": item.finished_at.isoformat() if item.finished_at else None,
                }
                for item in items
            ]
        }
    )
