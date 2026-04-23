from __future__ import annotations

from ..models import AccountBatch, AlertRecord, CurrentBinding, ExportJob, MobileAccount, OperationBatch
from .account_service import allocatable_batch_condition


def dashboard_summary():
    return {
        "available_accounts": (
            MobileAccount.query.join(AccountBatch)
            .filter(MobileAccount.status == "available", allocatable_batch_condition())
            .count()
        ),
        "assigned_accounts": MobileAccount.query.filter_by(status="assigned").count(),
        "current_bindings": CurrentBinding.query.count(),
        "pending_alerts": AlertRecord.query.filter_by(is_resolved=False).count(),
        "recent_batches": [
            {
                "id": batch.id,
                "batch_type": batch.batch_type,
                "status": batch.status,
                "success_rows": batch.success_rows,
                "failed_rows": batch.failed_rows,
                "created_at": batch.created_at.isoformat(),
            }
            for batch in OperationBatch.query.order_by(OperationBatch.id.desc()).limit(5).all()
        ],
        "recent_exports": [
            {"id": export.id, "filename": export.filename, "row_count": export.row_count}
            for export in ExportJob.query.order_by(ExportJob.id.desc()).limit(5).all()
        ],
    }
