import sys
from pathlib import Path
from io import BytesIO
from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app, db
from app.models import Account


def create_excel():
    wb = Workbook()
    ws = wb.active
    ws.append(["username", "password"])
    ws.append(["user1", "pass1"])
    b = BytesIO()
    wb.save(b)
    b.seek(0)
    return b


def test_import_accounts(tmp_path):
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()
    with app.test_client() as client:
        data = {
            "file": (create_excel(), "acc.xlsx"),
        }
        resp = client.post(
            "/accounts/import", data=data, content_type="multipart/form-data"
        )
        assert resp.status_code == 200
        assert resp.get_json()["imported"] == 1
        with app.app_context():
            assert Account.query.count() == 1
