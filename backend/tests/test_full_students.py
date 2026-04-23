from io import BytesIO
from datetime import datetime

import pandas as pd

from app.extensions import db
from app.models import AlertRecord, CurrentBinding, MobileAccount, Student
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


def test_full_students_preview_supports_chinese_headers(client, auth_headers):
    response = client.post(
        "/api/v1/full-students/import/preview",
        headers=auth_headers,
        data={
            "file": (
                excel_file(
                    [
                        {
                            "用户账号": "2023002002",
                            "用户名称": "赵六",
                            "到期日期": "2027-01-31",
                            "移动账号": "yd2002",
                        }
                    ]
                ),
                "full_cn.xlsx",
            )
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    assert response.json["data"]["preview"][0]["student_no"] == "2023002002"
    assert response.json["data"]["preview"][0]["name"] == "赵六"
    assert response.json["data"]["preview"][0]["expire_at"] == "2027-01-31"


def test_full_students_preview_uses_single_sheet_even_if_not_sheet1(client, auth_headers):
    buffer = BytesIO()
    dataframe = pd.DataFrame(
        [
            {
                "用户账号": "2023002003",
                "用户名称": "钱七",
                "到期日期": "2027-02-28",
            }
        ]
    )
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        dataframe.to_excel(writer, index=False, sheet_name=" 用户列表 ")
    buffer.seek(0)

    response = client.post(
        "/api/v1/full-students/import/preview",
        headers=auth_headers,
        data={"file": (buffer, "users.xls")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    assert response.json["data"]["preview"][0]["student_no"] == "2023002003"


def test_full_students_execute_binds_mobile_account_from_roster(client, auth_headers):
    client.post(
        "/api/v1/mobile-accounts/import",
        headers=auth_headers,
        data={
            "file": (
                excel_file([{"account": "yd3001", "batch_code": "202606"}]),
                "accounts.xlsx",
            )
        },
        content_type="multipart/form-data",
    )
    preview = client.post(
        "/api/v1/full-students/import/preview",
        headers=auth_headers,
        data={
            "file": (
                excel_file(
                    [
                        {
                            "student_no": "2023003001",
                            "name": "张三",
                            "expire_at": "2027-06-30",
                            "mobile_account": "yd3001",
                        }
                    ]
                ),
                "full_bind.xlsx",
            )
        },
        content_type="multipart/form-data",
    )
    assert preview.status_code == 201
    job_id = preview.json["data"]["job_id"]
    execute = client.post(
        f"/api/v1/full-students/import/{job_id}/execute",
        headers={**auth_headers, "X-Idempotency-Key": "full-students-bind-1"},
        json={"confirm": True},
    )
    assert execute.status_code == 200
    assert execute.json["data"]["success_rows"] == 1
    assert execute.json["data"]["conflicts"] == 0

    student = Student.query.filter_by(student_no="2023003001").first()
    assert student is not None
    binding = CurrentBinding.query.filter_by(student_id=student.id).first()
    assert binding is not None
    account = db.session.get(MobileAccount, binding.mobile_account_id)
    assert account is not None
    assert account.account == "yd3001"
    assert account.status == "assigned"


def test_full_students_execute_rebinds_to_roster_mobile_account(client, auth_headers):
    client.post(
        "/api/v1/mobile-accounts/import",
        headers=auth_headers,
        data={
            "file": (
                excel_file(
                    [
                        {"account": "yd4001", "batch_code": "202606"},
                        {"account": "yd4002", "batch_code": "202606"},
                    ]
                ),
                "accounts.xlsx",
            )
        },
        content_type="multipart/form-data",
    )

    charge_preview = client.post(
        "/api/v1/charge-batches/preview",
        headers=auth_headers,
        data={
            "file": (
                excel_file(
                    [
                        {
                            "student_no": "2023004001",
                            "name": "王五",
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
    batch_id = charge_preview.json["data"]["operation_batch_id"]
    client.post(
        f"/api/v1/charge-batches/{batch_id}/execute",
        headers={**auth_headers, "X-Idempotency-Key": "charge-rebind-1"},
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
                            "student_no": "2023004001",
                            "name": "王五",
                            "expire_at": "2027-07-31",
                            "mobile_account": "yd4002",
                        }
                    ]
                ),
                "full_rebind.xlsx",
            )
        },
        content_type="multipart/form-data",
    )
    assert full_preview.status_code == 201
    job_id = full_preview.json["data"]["job_id"]
    execute = client.post(
        f"/api/v1/full-students/import/{job_id}/execute",
        headers={**auth_headers, "X-Idempotency-Key": "full-students-rebind-1"},
        json={"confirm": True},
    )
    assert execute.status_code == 200
    assert execute.json["data"]["success_rows"] == 1
    assert execute.json["data"]["conflicts"] == 0

    student = Student.query.filter_by(student_no="2023004001").first()
    assert student is not None
    binding = CurrentBinding.query.filter_by(student_id=student.id).first()
    assert binding is not None
    current = db.session.get(MobileAccount, binding.mobile_account_id)
    assert current is not None
    assert current.account == "yd4002"
    assert MobileAccount.query.filter_by(account="yd4001").first().status == "available"
    assert MobileAccount.query.filter_by(account="yd4002").first().status == "assigned"


def test_full_students_execute_conflict_when_roster_account_taken_by_other_student(client, auth_headers):
    client.post(
        "/api/v1/mobile-accounts/import",
        headers=auth_headers,
        data={
            "file": (
                excel_file([{"account": "yd5001", "batch_code": "202606"}]),
                "accounts.xlsx",
            )
        },
        content_type="multipart/form-data",
    )

    first_preview = client.post(
        "/api/v1/full-students/import/preview",
        headers=auth_headers,
        data={
            "file": (
                excel_file(
                    [
                        {
                            "student_no": "2023005001",
                            "name": "赵一",
                            "expire_at": "2027-05-31",
                            "mobile_account": "yd5001",
                        }
                    ]
                ),
                "full_first.xlsx",
            )
        },
        content_type="multipart/form-data",
    )
    first_job_id = first_preview.json["data"]["job_id"]
    client.post(
        f"/api/v1/full-students/import/{first_job_id}/execute",
        headers={**auth_headers, "X-Idempotency-Key": "full-students-conflict-seed"},
        json={"confirm": True},
    )

    second_preview = client.post(
        "/api/v1/full-students/import/preview",
        headers=auth_headers,
        data={
            "file": (
                excel_file(
                    [
                        {
                            "student_no": "2023005002",
                            "name": "赵二",
                            "expire_at": "2027-05-31",
                            "mobile_account": "yd5001",
                        }
                    ]
                ),
                "full_conflict.xlsx",
            )
        },
        content_type="multipart/form-data",
    )
    second_job_id = second_preview.json["data"]["job_id"]
    execute = client.post(
        f"/api/v1/full-students/import/{second_job_id}/execute",
        headers={**auth_headers, "X-Idempotency-Key": "full-students-conflict-1"},
        json={"confirm": True},
    )
    assert execute.status_code == 200
    assert execute.json["data"]["success_rows"] == 0
    assert execute.json["data"]["conflicts"] == 1
    assert AlertRecord.query.count() >= 1


def test_full_students_preview_flags_duplicate_mobile_account_in_same_file(client, auth_headers):
    client.post(
        "/api/v1/mobile-accounts/import",
        headers=auth_headers,
        data={
            "file": (
                excel_file([{"account": "yd5002", "batch_code": "202606"}]),
                "accounts.xlsx",
            )
        },
        content_type="multipart/form-data",
    )

    preview = client.post(
        "/api/v1/full-students/import/preview",
        headers=auth_headers,
        data={
            "file": (
                excel_file(
                    [
                        {
                            "student_no": "2023005003",
                            "name": "赵三",
                            "expire_at": "2027-05-31",
                            "mobile_account": "yd5002",
                        },
                        {
                            "student_no": "2023005004",
                            "name": "赵四",
                            "expire_at": "2027-05-31",
                            "mobile_account": "yd5002",
                        },
                    ]
                ),
                "full_duplicate_account.xlsx",
            )
        },
        content_type="multipart/form-data",
    )
    assert preview.status_code == 201
    assert preview.json["data"]["conflict_count"] == 1
    assert preview.json["data"]["preview"][0]["conflict"] is False
    assert preview.json["data"]["preview"][1]["conflict"] is True
    assert preview.json["data"]["preview"][1]["conflict_message"] == "文件中同一移动账号被重复指定"
