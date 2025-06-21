import sys
import os
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
from app import create_app, db
from app.models import Account


def setup_accounts(app):
    with app.app_context():
        db.drop_all()
        db.create_all()
        account = Account(
            username="user1",
            password="pass1",
            is_bound=True,
            student_id="s1",
            bind_time=datetime.utcnow(),
        )
        db.session.add(account)
        db.session.commit()


def test_export_accounts():
    app = create_app()
    setup_accounts(app)
    with app.test_client() as client:
        resp = client.get("/export/accounts")
        assert resp.status_code == 200
        assert (
            resp.mimetype
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert len(resp.data) > 0
