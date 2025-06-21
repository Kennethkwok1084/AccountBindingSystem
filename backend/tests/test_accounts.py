import sys
import os
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
from app import create_app, db
from app.models import Account


def setup_data(app):
    with app.app_context():
        db.drop_all()
        db.create_all()
        acc1 = Account(
            username="u1",
            password="p1",
            is_bound=True,
            student_id="s1",
            bind_time=datetime.utcnow(),
        )
        acc2 = Account(username="u2", password="p2")
        acc3 = Account(
            username="abc",
            password="p3",
            is_bound=True,
            student_id="s2",
            bind_time=datetime.utcnow(),
        )
        db.session.add_all([acc1, acc2, acc3])
        db.session.commit()


def test_list_accounts_filters():
    app = create_app()
    setup_data(app)
    with app.test_client() as client:
        resp = client.get("/accounts?bound=true")
        data = resp.get_json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        resp = client.get("/accounts?bound=false")
        data = resp.get_json()
        assert data["total"] == 1


def test_list_accounts_search_and_pagination():
    app = create_app()
    setup_data(app)
    with app.test_client() as client:
        resp = client.get("/accounts?q=abc")
        data = resp.get_json()
        assert data["total"] == 1
        assert data["items"][0]["username"] == "abc"

        resp = client.get("/accounts?page=2&size=1")
        data = resp.get_json()
        assert data["total"] == 3
        assert len(data["items"]) == 1
