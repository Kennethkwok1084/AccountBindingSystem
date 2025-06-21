import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
from app import create_app, db
from app.models import BindingLog


def setup_logs(app):
    with app.app_context():
        db.drop_all()
        db.create_all()
        now = datetime.utcnow()
        log1 = BindingLog(
            username="u1",
            student_id="s1",
            action="bind",
            bind_time=now - timedelta(days=1),
        )
        log2 = BindingLog(username="u2", student_id="s2", action="bind", bind_time=now)
        db.session.add_all([log1, log2])
        db.session.commit()


def test_list_logs_filter():
    app = create_app()
    setup_logs(app)
    with app.test_client() as client:
        start = (datetime.utcnow() - timedelta(hours=12)).isoformat()
        resp = client.get(f"/logs?start={start}")
        data = resp.get_json()
        assert data["total"] == 1
        assert data["items"][0]["username"] == "u2"


def test_export_logs():
    app = create_app()
    setup_logs(app)
    with app.test_client() as client:
        resp = client.get("/export/logs")
        assert resp.status_code == 200
        assert (
            resp.mimetype
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert len(resp.data) > 0
