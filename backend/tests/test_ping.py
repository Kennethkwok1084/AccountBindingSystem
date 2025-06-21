import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
from app import create_app


def test_ping():
    app = create_app()
    with app.test_client() as client:
        resp = client.get("/ping")
        assert resp.status_code == 200
        assert resp.get_json() == {"message": "pong"}
