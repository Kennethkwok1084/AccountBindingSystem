from __future__ import annotations

from datetime import datetime

from flask import Blueprint, request

from ..extensions import db
from ..models import AlertRecord
from ..responses import success
from ..security import require_csrf, require_session


bp = Blueprint("alerts", __name__)


@bp.get("/alerts")
@require_session
def alerts():
    query = AlertRecord.query.order_by(AlertRecord.id.desc())
    if request.args.get("type"):
        query = query.filter(AlertRecord.type == request.args["type"])
    if request.args.get("is_resolved") is not None:
        query = query.filter(AlertRecord.is_resolved == (request.args.get("is_resolved") == "true"))
    items = query.all()
    return success(
        {
            "items": [
                {
                    "id": item.id,
                    "type": item.type,
                    "level": item.level,
                    "title": item.title,
                    "content": item.content,
                    "is_resolved": item.is_resolved,
                }
                for item in items
            ]
        }
    )


@bp.patch("/alerts/<int:alert_id>/resolve")
@require_session
@require_csrf
def resolve_alert(alert_id: int):
    alert = AlertRecord.query.get_or_404(alert_id)
    payload = request.get_json(silent=True) or {}
    alert.is_resolved = True
    alert.status = "resolved"
    alert.resolution_note = payload.get("resolution_note")
    alert.resolved_at = datetime.utcnow()
    db.session.commit()
    return success({"id": alert.id, "is_resolved": alert.is_resolved})

