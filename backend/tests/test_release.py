import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _set_db(path):
    os.environ["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{path}"


from app import create_app, db
from app.models import Account, BindingLog


def test_auto_release(tmp_path):
    db_path = tmp_path / "app.db"
    _set_db(db_path)
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()
        old_time = datetime.utcnow() - timedelta(days=33)
        account = Account(
            username="old",
            password="pass",
            is_bound=True,
            student_id="1001",
            bind_time=old_time,
        )
        db.session.add(account)
        db.session.commit()

    with app.test_client() as client:
        resp = client.post("/auto-release")
        assert resp.status_code == 200
        assert resp.get_json()["released"] == 1

    with app.app_context():
        acc = Account.query.filter_by(username="old").first()
        assert not acc.is_bound
        assert acc.student_id is None
        log = BindingLog.query.filter_by(username="old", action="auto_release").first()
        assert log is not None
