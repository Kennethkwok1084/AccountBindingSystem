import sys
import os
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
from app import create_app, db
from app.models import Account, BindingLog


def create_excel():
    wb = Workbook()
    ws = wb.active
    ws.append(["绑定账户", "账号", "密码", "备注"])
    ws.append(["stu1", "user1", "pass1", "old"])
    b = BytesIO()
    wb.save(b)
    b.seek(0)
    return b


def create_logs_excel():
    wb = Workbook()
    ws = wb.active
    ws.append(
        [
            "用户账号",
            "移动账号",
            "收费时间",
            "费用类型",
            "收费金额（元）",
            "收费方式",
            "经手人",
            "收费操作员",
            "收费备注",
            "业务类型",
        ]
    )
    ws.append(["u1", "m1", "", "", "", "", "", "", "", ""])
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
            acc = Account.query.filter_by(username="user1").first()
            assert acc is not None
            assert acc.student_id == "stu1"
            assert acc.is_bound


def test_import_logs(tmp_path):
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()
    with app.test_client() as client:
        data = {
            "file": (create_logs_excel(), "移动06231000.xlsx"),
        }
        resp = client.post(
            "/logs/import", data=data, content_type="multipart/form-data"
        )
        assert resp.status_code == 200
        assert resp.get_json()["imported"] == 1
        with app.app_context():
            log = BindingLog.query.first()
            assert log.username == "m1"
            assert log.student_id == "u1"
            assert log.bind_time.month == 6
            assert log.bind_time.day == 23
            assert log.bind_time.hour == 10
            assert log.bind_time.minute == 0
