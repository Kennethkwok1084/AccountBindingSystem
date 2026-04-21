from datetime import datetime

from app.models import AccountBatch, CurrentBinding, ExportJob, MobileAccount, Student
from .conftest import excel_file


def test_import_accounts_and_charge_execute(client, auth_headers):
    account_file = excel_file(
        [
            {
                "account": "yd0001",
                "batch_code": "202604",
            },
            {
                "account": "yd0002",
                "batch_code": "202604",
            },
        ]
    )
    response = client.post(
        "/api/v1/mobile-accounts/import",
        headers=auth_headers,
        data={"file": (account_file, "accounts.xlsx")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 201

    charge_file = excel_file(
        [
            {
                "student_no": "2023001001",
                "name": "张三",
                "charge_time": datetime(2026, 4, 20, 9, 0, 0),
                "package_name": "包月套餐",
                "fee_amount": 30,
            }
        ]
    )
    preview = client.post(
        "/api/v1/charge-batches/preview",
        headers=auth_headers,
        data={"file": (charge_file, "charge.xlsx")},
        content_type="multipart/form-data",
    )
    assert preview.status_code == 201
    batch_id = preview.json["data"]["operation_batch_id"]
    execute = client.post(
        f"/api/v1/charge-batches/{batch_id}/execute",
        headers={**auth_headers, "X-Idempotency-Key": "test-charge-1"},
        json={"confirm": True},
    )
    assert execute.status_code == 200
    assert execute.json["data"]["success_count"] == 1
    assert Student.query.filter_by(student_no="2023001001").first() is not None
    assert CurrentBinding.query.count() == 1
    assert ExportJob.query.count() == 1


def test_charge_batch_enforces_top_20_limit(client, auth_headers):
    account_rows = [
        {
            "account": f"yd{i:04d}",
            "batch_code": "202605",
        }
        for i in range(1, 30)
    ]
    client.post(
        "/api/v1/mobile-accounts/import",
        headers=auth_headers,
        data={"file": (excel_file(account_rows), "accounts.xlsx")},
        content_type="multipart/form-data",
    )
    charge_rows = [
        {
            "student_no": f"2023001{i:03d}",
            "name": f"学生{i}",
            "charge_time": datetime(2026, 4, 20, 9, i % 60, 0),
            "package_name": "包月套餐",
            "fee_amount": 30,
        }
        for i in range(1, 26)
    ]
    preview = client.post(
        "/api/v1/charge-batches/preview",
        headers=auth_headers,
        data={"file": (excel_file(charge_rows), "charge.xlsx")},
        content_type="multipart/form-data",
    )
    assert preview.status_code == 201
    assert preview.json["data"]["fail_count"] == 5
