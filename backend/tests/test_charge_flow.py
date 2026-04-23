from datetime import datetime

from app.extensions import db
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


def test_charge_batch_preview_assigns_unique_accounts_without_hard_limit(client, auth_headers):
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
    assert preview.json["data"]["fail_count"] == 0
    assert preview.json["data"]["to_allocate_count"] == 25
    allocate_account_ids = [
        row["new_mobile_account_id"]
        for row in preview.json["data"]["details"]
        if row["action_plan"] == "allocate"
    ]
    assert len(allocate_account_ids) == 25
    assert len(set(allocate_account_ids)) == 25


def test_charge_preview_supports_chinese_headers_and_optional_name(client, auth_headers):
    client.post(
        "/api/v1/mobile-accounts/import",
        headers=auth_headers,
        data={
            "file": (
                excel_file(
                    [
                        {
                            "account": "yd9001",
                            "batch_code": "202607",
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
                            "用户账号": "2023009001",
                            "收费时间": datetime(2026, 4, 20, 9, 0, 0),
                            "费用类型": "包月套餐",
                            "收费金额（元）": 30,
                        }
                    ]
                ),
                "charge_cn.xls",
            )
        },
        content_type="multipart/form-data",
    )
    assert preview.status_code == 201
    assert preview.json["data"]["preview_rows"] == 1
    assert preview.json["data"]["to_allocate_count"] == 1


def test_charge_preview_returns_import_errors_for_partial_valid_rows(client, auth_headers):
    client.post(
        "/api/v1/mobile-accounts/import",
        headers=auth_headers,
        data={
            "file": (
                excel_file(
                    [
                        {
                            "account": "yd9010",
                            "batch_code": "202607",
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
                            "student_no": "2023009010",
                            "name": "学生A",
                            "charge_time": datetime(2026, 4, 20, 9, 0, 0),
                            "package_name": "包月套餐",
                            "fee_amount": 30,
                        },
                        {
                            "student_no": "2023009011",
                            "name": "学生B",
                            "charge_time": datetime(2026, 4, 20, 9, 1, 0),
                            "package_name": "包月套餐",
                            "fee_amount": -1,
                        },
                    ]
                ),
                "charge-mixed.xlsx",
            )
        },
        content_type="multipart/form-data",
    )

    assert preview.status_code == 201
    assert preview.json["data"]["preview_rows"] == 1
    assert preview.json["data"]["import_error_count"] == 1
    assert preview.json["data"]["import_errors"][0]["row_no"] == 3
    assert preview.json["data"]["import_errors"][0]["field_name"] == "fee_amount"


def test_charge_batch_execute_rebinds_expired_students_to_unique_accounts(client, auth_headers):
    client.post(
        "/api/v1/mobile-accounts/import",
        headers=auth_headers,
        data={
            "file": (
                excel_file(
                    [
                        {"account": "yd7001", "batch_code": "202604"},
                        {"account": "yd7002", "batch_code": "202604"},
                    ]
                ),
                "accounts-old.xlsx",
            )
        },
        content_type="multipart/form-data",
    )

    first_charge = client.post(
        "/api/v1/charge-batches/preview",
        headers=auth_headers,
        data={
            "file": (
                excel_file(
                    [
                        {
                            "student_no": "2023007001",
                            "name": "学生1",
                            "charge_time": datetime(2026, 4, 20, 9, 0, 0),
                            "package_name": "包月套餐",
                            "fee_amount": 30,
                        },
                        {
                            "student_no": "2023007002",
                            "name": "学生2",
                            "charge_time": datetime(2026, 4, 20, 9, 1, 0),
                            "package_name": "包月套餐",
                            "fee_amount": 30,
                        },
                    ]
                ),
                "charge-first.xlsx",
            )
        },
        content_type="multipart/form-data",
    )
    first_batch_id = first_charge.json["data"]["operation_batch_id"]
    first_execute = client.post(
        f"/api/v1/charge-batches/{first_batch_id}/execute",
        headers={**auth_headers, "X-Idempotency-Key": "charge-rebind-seed"},
        json={"confirm": True},
    )
    assert first_execute.status_code == 200
    assert first_execute.json["data"]["success_count"] == 2

    client.post(
        "/api/v1/mobile-accounts/import",
        headers=auth_headers,
        data={
            "file": (
                excel_file(
                    [
                        {"account": "yd7003", "batch_code": "202605"},
                        {"account": "yd7004", "batch_code": "202605"},
                    ]
                ),
                "accounts-new.xlsx",
            )
        },
        content_type="multipart/form-data",
    )

    second_charge = client.post(
        "/api/v1/charge-batches/preview",
        headers=auth_headers,
        data={
            "file": (
                excel_file(
                    [
                        {
                            "student_no": "2023007001",
                            "name": "学生1",
                            "charge_time": datetime(2026, 6, 25, 9, 0, 0),
                            "package_name": "包月套餐",
                            "fee_amount": 30,
                        },
                        {
                            "student_no": "2023007002",
                            "name": "学生2",
                            "charge_time": datetime(2026, 6, 25, 9, 1, 0),
                            "package_name": "包月套餐",
                            "fee_amount": 30,
                        },
                    ]
                ),
                "charge-second.xlsx",
            )
        },
        content_type="multipart/form-data",
    )
    assert second_charge.status_code == 201
    assert second_charge.json["data"]["to_rebind_count"] == 2
    preview_rebind_ids = [
        row["new_mobile_account_id"]
        for row in second_charge.json["data"]["details"]
        if row["action_plan"] == "rebind"
    ]
    assert len(preview_rebind_ids) == 2
    assert len(set(preview_rebind_ids)) == 2

    second_batch_id = second_charge.json["data"]["operation_batch_id"]
    second_execute = client.post(
        f"/api/v1/charge-batches/{second_batch_id}/execute",
        headers={**auth_headers, "X-Idempotency-Key": "charge-rebind-execute"},
        json={"confirm": True},
    )
    assert second_execute.status_code == 200
    assert second_execute.json["data"]["success_count"] == 2

    bindings = CurrentBinding.query.order_by(CurrentBinding.student_id.asc()).all()
    assert len(bindings) == 2
    current_accounts = [db.session.get(MobileAccount, binding.mobile_account_id).account for binding in bindings]
    assert set(current_accounts) == {"yd7003", "yd7004"}
    assert MobileAccount.query.filter_by(account="yd7001").first().status == "available"
    assert MobileAccount.query.filter_by(account="yd7002").first().status == "available"
