from datetime import datetime

from app.models import CurrentBinding, MobileAccount
from .conftest import excel_file


def test_full_students_release_expired_binding(client, auth_headers):
    client.post(
        "/api/v1/mobile-accounts/import",
        headers=auth_headers,
        data={
            "file": (
                excel_file(
                    [
                        {
                            "account": "yd1000",
                            "batch_code": "202606",
                        }
                    ]
                ),
                "accounts.xlsx",
            )
        },
        content_type="multipart/form-data",
    )
    preview = client.post(
        "/api/v1/charge-batches/preview",
        headers=auth_headers,
        data={
            "file": (
                excel_file(
                    [
                        {
                            "student_no": "2023002001",
                            "name": "李四",
                            "charge_time": datetime(2026, 4, 20, 9, 0, 0),
                            "package_name": "包月套餐",
                            "fee_amount": 30,
                        }
                    ]
                ),
                "charge.xlsx",
            )
        },
        content_type="multipart/form-data",
    )
    batch_id = preview.json["data"]["operation_batch_id"]
    client.post(
        f"/api/v1/charge-batches/{batch_id}/execute",
        headers={**auth_headers, "X-Idempotency-Key": "charge-full-list"},
        json={"confirm": True},
    )

    full_preview = client.post(
        "/api/v1/full-students/import/preview",
        headers=auth_headers,
        data={
            "file": (
                excel_file(
                    [
                        {
                            "student_no": "2023002001",
                            "name": "李四",
                            "expire_at": "2020-01-01",
                        }
                    ]
                ),
                "full.xlsx",
            )
        },
        content_type="multipart/form-data",
    )
    assert full_preview.status_code == 201
    job_id = full_preview.json["data"]["job_id"]
    execute = client.post(
        f"/api/v1/full-students/import/{job_id}/execute",
        headers={**auth_headers, "X-Idempotency-Key": "full-students-1"},
        json={"confirm": True},
    )
    assert execute.status_code == 200
    assert CurrentBinding.query.count() == 0
    assert MobileAccount.query.filter_by(account="yd1000").first().status == "available"

    execute_again = client.post(
        f"/api/v1/full-students/import/{job_id}/execute",
        headers={**auth_headers, "X-Idempotency-Key": "full-students-2"},
        json={"confirm": True},
    )
    assert execute_again.status_code == 409
