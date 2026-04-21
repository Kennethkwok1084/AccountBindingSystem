from __future__ import annotations

from flask import Blueprint

from ..responses import success
from ..security import require_session
from ..services.dashboard_service import dashboard_summary


bp = Blueprint("dashboard", __name__)


@bp.get("/dashboard")
@require_session
def dashboard():
    return success(dashboard_summary())

