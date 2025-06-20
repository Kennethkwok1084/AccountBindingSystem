"""Placeholder for release task."""

from datetime import datetime, timedelta

from app import create_app, db
from app.models import Account, BindingLog


def auto_release(days: int = 32) -> None:
    app = create_app()
    with app.app_context():
        cutoff = datetime.utcnow() - timedelta(days=days)
        accounts = Account.query.filter(
            Account.is_bound.is_(True), Account.bind_time < cutoff
        )
        for account in accounts:
            account.is_bound = False
            account.student_id = None
            account.bind_time = None
            log = BindingLog(
                username=account.username,
                student_id=None,
                action="auto_release",
            )
            db.session.add(log)
        db.session.commit()
