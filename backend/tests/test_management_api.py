from io import BytesIO
import pandas as pd
from datetime import date, datetime, timedelta
from pathlib import Path

from app.extensions import db
from app.models import AccountBatch, BindingHistory, CurrentBinding, ExportJob, MobileAccount
from app.services.scheduler_service import run_binding_expire_release, run_cleanup_temp_files
from .conftest import excel_file


def test_batches_and_import_detail(client, auth_headers):
    create = client.post(
        "/api/v1/batches",
        headers=auth_headers,
        json={
            "batch_code": "B202700",
            "batch_name": "测试批次",
            "batch_type": "normal",
            "priority": 120,
            "warn_days": 3,
            "expire_at": "2027-01-01",
        },
    )
    assert create.status_code == 201
    batch_id = create.json["data"]["id"]

    update = client.put(
        f"/api/v1/batches/{batch_id}",
        headers=auth_headers,
        json={"priority": 80, "warn_days": 5, "remark": "updated"},
    )
    assert update.status_code == 200
    assert update.json["data"]["priority"] == 80
    assert update.json["data"]["warn_days"] == 5

    account_import = client.post(
        "/api/v1/mobile-accounts/import",
        headers=auth_headers,
        data={
            "file": (
                excel_file(
                    [
                        {
                            "account": "yd3000",
                            "batch_code": "202604",
                        }
                    ]
                ),
                "accounts.xlsx",
            )
        },
        content_type="multipart/form-data",
    )
    assert account_import.status_code == 201
    job_id = account_import.json["data"]["job_id"]

    detail = client.get(f"/api/v1/imports/{job_id}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json["data"]["job"]["job_type"] == "account_pool"
    assert detail.json["data"]["errors"]["total"] == 0
    imported_batch = AccountBatch.query.filter_by(batch_code="202604").first()
    assert imported_batch.batch_name == "202604"
    assert imported_batch.batch_type == "normal"
    assert imported_batch.priority == 797395
    assert imported_batch.warn_days == 1
    assert imported_batch.expire_at.isoformat() == "2026-04-30"


def test_account_import_returns_concrete_template_error(client, auth_headers):
    response = client.post(
        "/api/v1/mobile-accounts/import",
        headers=auth_headers,
        data={
            "file": (
                excel_file(
                    [
                        {
                            "account": "yd3001",
                            "batch_name": "202604",
                        }
                    ]
                ),
                "accounts.xlsx",
            )
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 422
    assert response.json["message"] == "缺少必填列：batch_code"
    assert response.json["details"][0]["error_code"] == "missing_required_column"
    assert response.json["details"][0]["field_name"] == "batch_code"


def test_account_import_supports_special_zero_batch_and_nat_error_rows(client, auth_headers):
    response = client.post(
        "/api/v1/mobile-accounts/import",
        headers=auth_headers,
        data={
            "file": (
                excel_file(
                    [
                        {
                            "account": "yd3002",
                            "batch_code": "0元账户",
                        },
                        {
                            "account": "bad account",
                            "batch_code": "202605",
                            "expire_at": pd.NaT,
                        },
                    ]
                ),
                "accounts.xlsx",
            )
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    assert response.json["data"]["success_rows"] == 1
    assert response.json["data"]["failed_rows"] == 1
    zero_batch = AccountBatch.query.filter_by(batch_code="0元账户").first()
    assert zero_batch.batch_name == "0元账户"
    assert zero_batch.priority == 0
    assert zero_batch.expire_at.isoformat() == "2099-01-01"
    detail = client.get(f"/api/v1/imports/{response.json['data']['job_id']}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json["data"]["errors"]["total"] == 1


def test_account_template_download(client, auth_headers):
    response = client.get("/api/v1/mobile-accounts/template", headers=auth_headers)
    assert response.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in response.content_type
    dataframe = pd.read_excel(BytesIO(response.data))
    assert list(dataframe.columns) == ["account", "batch_code"]


def test_manual_rebind_and_scheduler_jobs(client, auth_headers, app):
    client.post(
        "/api/v1/mobile-accounts/import",
        headers=auth_headers,
        data={
            "file": (
                excel_file(
                    [
                        {
                            "account": "yd4000",
                            "batch_code": "202604",
                        },
                        {
                            "account": "yd4001",
                            "batch_code": "202605",
                        },
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
                            "student_no": "2023005001",
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
    batch_id = preview.json["data"]["operation_batch_id"]
    client.post(
        f"/api/v1/charge-batches/{batch_id}/execute",
        headers={**auth_headers, "X-Idempotency-Key": "charge-manual-1"},
        json={"confirm": True},
    )

    second_account = MobileAccount.query.filter_by(account="yd4001").first()
    manual = client.post(
        "/api/v1/bindings/manual-rebind",
        headers={**auth_headers, "X-Idempotency-Key": "manual-1"},
        json={
            "student_no": "2023005001",
            "new_account_id": second_account.id,
            "old_account_action": "disable",
            "remark": "异常换绑",
        },
    )
    assert manual.status_code == 200
    assert ExportJob.query.count() == 2

    binding = CurrentBinding.query.first()
    binding.expire_at = date.today() - timedelta(days=1)
    db.session.commit()
    with app.app_context():
        message = run_binding_expire_release()
        assert "released 1 bindings" in message
        assert CurrentBinding.query.count() == 0
        assert BindingHistory.query.filter_by(action_type="release").count() >= 1

        tmp_file = Path(app.config["STORAGE_ROOT"]) / "tmp" / "old.tmp"
        tmp_file.write_text("old")
        old_ts = (datetime.now() - timedelta(days=10)).timestamp()
        tmp_file.chmod(0o644)
        Path(tmp_file).touch()
        import os

        os.utime(tmp_file, (old_ts, old_ts))
        cleanup_message = run_cleanup_temp_files()
        assert "removed=1" in cleanup_message
        assert not tmp_file.exists()


def test_scheduler_manual_run_requires_idempotency_key(client, auth_headers):
    response = client.post("/api/v1/scheduler/run/inventory_alert_scan", headers=auth_headers, json={})
    assert response.status_code == 400


def test_students_list_endpoint(client, auth_headers):
    client.post(
        "/api/v1/mobile-accounts/import",
        headers=auth_headers,
        data={
            "file": (
                excel_file(
                    [
                        {
                            "account": "yd5100",
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
                            "student_no": "2023005100",
                            "name": "测试学生",
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
    execute = client.post(
        f"/api/v1/charge-batches/{batch_id}/execute",
        headers={**auth_headers, "X-Idempotency-Key": "charge-student-list-1"},
        json={"confirm": True},
    )
    assert execute.status_code == 200

    response = client.get("/api/v1/students", headers=auth_headers)
    assert response.status_code == 200
    assert response.json["data"]["total"] >= 1
    target = next((item for item in response.json["data"]["items"] if item["student_no"] == "2023005100"), None)
    assert target is not None
    assert target["name"] == "测试学生"
    assert target["current_mobile_account"] == "yd5100"


def test_batch_rebind_preview_and_execute_keep_target_accounts_unique(client, auth_headers):
    client.post(
        "/api/v1/mobile-accounts/import",
        headers=auth_headers,
        data={
            "file": (
                excel_file(
                    [
                        {"account": "yd6101", "batch_code": "202604"},
                        {"account": "yd6102", "batch_code": "202604"},
                    ]
                ),
                "accounts-old.xlsx",
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
                            "student_no": "2023006101",
                            "name": "甲",
                            "charge_time": datetime(2026, 4, 20, 9, 0, 0),
                            "package_name": "包月套餐",
                            "fee_amount": 30,
                        },
                        {
                            "student_no": "2023006102",
                            "name": "乙",
                            "charge_time": datetime(2026, 4, 20, 9, 1, 0),
                            "package_name": "包月套餐",
                            "fee_amount": 30,
                        },
                    ]
                ),
                "charge.xlsx",
            )
        },
        content_type="multipart/form-data",
    )
    charge_batch_id = charge_preview.json["data"]["operation_batch_id"]
    charge_execute = client.post(
        f"/api/v1/charge-batches/{charge_batch_id}/execute",
        headers={**auth_headers, "X-Idempotency-Key": "batch-rebind-seed"},
        json={"confirm": True},
    )
    assert charge_execute.status_code == 200

    client.post(
        "/api/v1/mobile-accounts/import",
        headers=auth_headers,
        data={
            "file": (
                excel_file(
                    [
                        {"account": "yd6103", "batch_code": "202605"},
                        {"account": "yd6104", "batch_code": "202605"},
                    ]
                ),
                "accounts-new.xlsx",
            )
        },
        content_type="multipart/form-data",
    )

    old_batch = AccountBatch.query.filter_by(batch_code="202604").first()
    preview = client.post(
        "/api/v1/batch-rebinds/preview",
        headers=auth_headers,
        json={"batch_id": old_batch.id},
    )
    assert preview.status_code == 200
    suggested_accounts = [item["new_account"] for item in preview.json["data"]["items"] if item["new_account"]]
    assert suggested_accounts == ["yd6103", "yd6104"]
    assert len(suggested_accounts) == len(set(suggested_accounts))

    execute = client.post(
        f"/api/v1/batch-rebinds/{old_batch.id}/execute",
        headers={**auth_headers, "X-Idempotency-Key": "batch-rebind-execute"},
        json={"confirm": True},
    )
    assert execute.status_code == 200
    assert execute.json["data"]["success_rows"] == 2
    assert execute.json["data"]["failed_rows"] == 0

    bindings = CurrentBinding.query.order_by(CurrentBinding.student_id.asc()).all()
    rebound_accounts = {db.session.get(MobileAccount, binding.mobile_account_id).account for binding in bindings}
    assert rebound_accounts == {"yd6103", "yd6104"}
    assert MobileAccount.query.filter_by(account="yd6101").first().status == "expired"
    assert MobileAccount.query.filter_by(account="yd6102").first().status == "expired"
