from io import BytesIO
import pandas as pd
from datetime import date, datetime, timedelta
from pathlib import Path
import logging
from types import SimpleNamespace

from app.extensions import db
from app.models import AccountBatch, BindingHistory, CurrentBinding, ExportJob, MobileAccount
from app.services.audit_service import write_audit
from app.services.config_service import set_config_value
from app.services.scheduler_service import run_binding_expire_release, run_cleanup_temp_files
from app.services import syslog_service
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
    assert imported_batch.priority == 202604
    assert imported_batch.warn_days == 1
    assert imported_batch.expire_at.isoformat() == "2027-04-30"


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


def test_student_ledger_export_creates_excel_job(client, auth_headers):
    client.post(
        "/api/v1/mobile-accounts/import",
        headers=auth_headers,
        data={
            "file": (
                excel_file(
                    [
                        {
                            "account": "yd-student-ledger-001",
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
                            "student_no": "2023010001",
                            "name": "导出台账学生",
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
        headers={**auth_headers, "X-Idempotency-Key": "student-ledger-export"},
        json={"confirm": True},
    )

    response = client.post(
        "/api/v1/students/export",
        headers=auth_headers,
        json={"keyword": "2023010001"},
    )
    assert response.status_code == 201
    export_id = response.json["data"]["export_job"]["id"]
    export_job = db.session.get(ExportJob, export_id)
    dataframe = pd.read_excel(export_job.stored_path)
    assert list(dataframe.columns) == ["学号", "姓名", "当前账号", "绑定到期", "来源到期", "预期到期"]
    assert str(dataframe.iloc[0]["学号"]) == "2023010001"

    exports_response = client.get(
        f"/api/v1/exports?keyword={response.json['data']['export_job']['filename']}",
        headers=auth_headers,
    )
    assert exports_response.status_code == 200
    assert exports_response.json["data"]["total"] == 1
    assert exports_response.json["data"]["items"][0]["filename"] == response.json["data"]["export_job"]["filename"]


def test_account_ledger_export_creates_excel_job(client, auth_headers):
    client.post(
        "/api/v1/mobile-accounts/import",
        headers=auth_headers,
        data={
            "file": (
                excel_file(
                    [
                        {
                            "account": "yd-ledger-001",
                            "batch_code": "202606",
                        }
                    ]
                ),
                "accounts.xlsx",
            )
        },
        content_type="multipart/form-data",
    )

    response = client.post(
        "/api/v1/mobile-accounts/export",
        headers=auth_headers,
        json={"account": "yd-ledger-001"},
    )
    assert response.status_code == 201
    export_id = response.json["data"]["export_job"]["id"]
    export_job = db.session.get(ExportJob, export_id)
    dataframe = pd.read_excel(export_job.stored_path)
    assert list(dataframe.columns) == ["账号", "状态", "批次编码", "批次类型", "批次状态", "批次到期日", "最近分配时间"]
    assert dataframe.iloc[0]["账号"] == "yd-ledger-001"


def test_student_history_export_creates_excel_job(client, auth_headers):
    client.post(
        "/api/v1/mobile-accounts/import",
        headers=auth_headers,
        data={"file": (excel_file([{"account": "yd-his-001", "batch_code": "202606"}]), "accounts.xlsx")},
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
                            "student_no": "2023010002",
                            "name": "历史学生",
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
        headers={**auth_headers, "X-Idempotency-Key": "student-history-export"},
        json={"confirm": True},
    )

    response = client.post(
        "/api/v1/students/2023010002/history/export",
        headers=auth_headers,
        json={},
    )
    assert response.status_code == 201
    export_job = db.session.get(ExportJob, response.json["data"]["export_job"]["id"])
    dataframe = pd.read_excel(export_job.stored_path)
    assert list(dataframe.columns) == ["学号", "姓名", "时间", "动作", "旧账号ID", "旧账号", "新账号ID", "新账号"]
    assert str(dataframe.iloc[0]["学号"]) == "2023010002"


def test_account_history_export_creates_excel_job(client, auth_headers):
    client.post(
        "/api/v1/mobile-accounts/import",
        headers=auth_headers,
        data={
            "file": (
                excel_file(
                    [
                        {"account": "yd-his-acc-001", "batch_code": "202606"},
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
                            "student_no": "2023010003",
                            "name": "历史账号学生",
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
        headers={**auth_headers, "X-Idempotency-Key": "account-history-export"},
        json={"confirm": True},
    )
    account_name = execute.json["data"]["export_job"]["filename"]  # placeholder to keep execute used
    assert account_name

    response = client.post(
        "/api/v1/ledger/accounts/yd-his-acc-001/export",
        headers=auth_headers,
        json={},
    )
    assert response.status_code == 201
    export_job = db.session.get(ExportJob, response.json["data"]["export_job"]["id"])
    dataframe = pd.read_excel(export_job.stored_path)
    assert list(dataframe.columns) == ["账号", "时间", "动作", "学号", "姓名", "旧账号ID", "旧账号", "新账号ID", "新账号"]
    assert dataframe.iloc[0]["账号"] == "yd-his-acc-001"


def test_audit_logs_export_creates_excel_job(client, auth_headers):
    client.put(
        "/api/v1/config",
        headers=auth_headers,
        json={"package.month_days": 32},
    )

    response = client.post(
        "/api/v1/audit-logs/export",
        headers=auth_headers,
        json={"action": "update_config"},
    )
    assert response.status_code == 201
    export_job = db.session.get(ExportJob, response.json["data"]["export_job"]["id"])
    dataframe = pd.read_excel(export_job.stored_path)
    assert list(dataframe.columns) == ["ID", "动作", "资源类型", "资源ID", "操作人ID", "详情", "时间"]
    assert "update_config" in set(dataframe["动作"].astype(str))


def test_config_metadata_contains_chinese_labels_and_types(client, auth_headers):
    response = client.get("/api/v1/config", headers=auth_headers)
    assert response.status_code == 200
    assert response.json["data"]["package.month_days"]["label"] == "包月天数"
    assert response.json["data"]["package.month_days"]["type"] == "number"
    assert response.json["data"]["integration.syslog.enabled"]["label"] == "启用 Syslog 转发"
    assert response.json["data"]["integration.syslog.enabled"]["type"] == "boolean"


def test_write_audit_emits_syslog_when_enabled(app, monkeypatch):
    emitted = {}

    class FakeHandler:
        LOG_USER = 1
        LOG_LOCAL0 = 16

        def __init__(self, address, facility, socktype):
            emitted["address"] = address
            emitted["facility"] = facility
            emitted["socktype"] = socktype

        def setFormatter(self, formatter):
            emitted["formatter"] = formatter

        def close(self):
            emitted["closed"] = True

    class FakeLogger:
        def __init__(self):
            self.handlers = []
            self.propagate = False
            self.level = None

        def setLevel(self, level):
            self.level = level

        def info(self, message):
            emitted["message"] = message

    fake_logger = FakeLogger()

    monkeypatch.setattr(syslog_service, "SysLogHandler", FakeHandler)
    monkeypatch.setattr(
        syslog_service,
        "logging",
        SimpleNamespace(
            INFO=logging.INFO,
            Formatter=lambda pattern: pattern,
            getLogger=lambda _name=None: fake_logger,
        ),
    )

    with app.app_context():
        set_config_value("integration.syslog.enabled", True)
        set_config_value("integration.syslog.host", "127.0.0.1")
        set_config_value("integration.syslog.port", 1514)
        set_config_value("integration.syslog.protocol", "udp")
        set_config_value("integration.syslog.facility", "local0")
        set_config_value("integration.syslog.app_name", "abs-test")

        write_audit("test_syslog", "system", "1", {"hello": "world"}, operator_id=1)

    assert emitted["address"] == ("127.0.0.1", 1514)
    assert emitted["socktype"] is not None
    assert fake_logger.level == logging.INFO
    assert '"event_type": "audit_log"' in emitted["message"]
    assert '"action": "test_syslog"' in emitted["message"]
    assert emitted["closed"] is True


def test_test_syslog_connectivity_endpoint_uses_payload_values(client, auth_headers, monkeypatch):
    emitted = {}

    class FakeHandler:
        LOG_USER = 1
        LOG_LOCAL0 = 16

        def __init__(self, address, facility, socktype):
            emitted["address"] = address
            emitted["facility"] = facility
            emitted["socktype"] = socktype

        def setFormatter(self, formatter):
            emitted["formatter"] = formatter

        def close(self):
            emitted["closed"] = True

    class FakeLogger:
        def __init__(self):
            self.handlers = []
            self.propagate = False
            self.level = None

        def setLevel(self, level):
            self.level = level

        def info(self, message):
            emitted["message"] = message

    fake_logger = FakeLogger()
    monkeypatch.setattr(syslog_service, "SysLogHandler", FakeHandler)
    monkeypatch.setattr(
        syslog_service,
        "logging",
        SimpleNamespace(
            INFO=logging.INFO,
            Formatter=lambda pattern: pattern,
            getLogger=lambda _name=None: fake_logger,
        ),
    )

    response = client.post(
        "/api/v1/config/test-syslog",
        headers=auth_headers,
        json={
            "integration.syslog.enabled": False,
            "integration.syslog.host": "10.0.0.8",
            "integration.syslog.port": 5514,
            "integration.syslog.protocol": "tcp",
            "integration.syslog.facility": "local0",
            "integration.syslog.app_name": "abs-ui-test",
        },
    )

    assert response.status_code == 200
    assert response.json["data"]["host"] == "10.0.0.8"
    assert response.json["data"]["port"] == 5514
    assert response.json["data"]["protocol"] == "tcp"
    assert emitted["address"] == ("10.0.0.8", 5514)
    assert '"event_type": "syslog_connectivity_test"' in emitted["message"]


def test_batch_list_marks_past_expire_batches_as_expired(client, auth_headers):
    create = client.post(
        "/api/v1/batches",
        headers=auth_headers,
        json={
            "batch_code": "B202401",
            "batch_name": "过期批次",
            "batch_type": "normal",
            "priority": 10,
            "warn_days": 1,
            "expire_at": "2020-01-31",
            "status": "active",
        },
    )
    assert create.status_code == 201

    response = client.get("/api/v1/batches?status=expired", headers=auth_headers)
    assert response.status_code == 200
    assert response.json["data"]["items"][0]["status"] == "expired"
    assert response.json["data"]["items"][0]["raw_status"] == "active"


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

    manual = client.post(
        "/api/v1/bindings/manual-rebind",
        headers={**auth_headers, "X-Idempotency-Key": "manual-1"},
        json={
            "student_no": "2023005001",
            "old_account_action": "disable",
            "remark": "异常换绑",
        },
    )
    assert manual.status_code == 200
    assert manual.json["data"]["old_account"] == "yd4001"
    assert manual.json["data"]["new_account"] == "yd4000"
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
