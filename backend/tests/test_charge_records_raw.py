from __future__ import annotations

from datetime import datetime
from io import BytesIO

import pandas as pd

from app.extensions import db
from app.models import ChargeRawRecord, ExportJob
from .conftest import excel_file


def _excel_bytes(rows: list[dict]) -> bytes:
    buffer = BytesIO()
    pd.DataFrame(rows).to_excel(buffer, index=False)
    return buffer.getvalue()


def _upload(client, auth_headers, content: bytes, filename: str = "charge-raw.xlsx"):
    return client.post(
        "/api/v1/charge-record-imports",
        headers=auth_headers,
        data={"file": (BytesIO(content), filename)},
        content_type="multipart/form-data",
    )


def test_charge_raw_import_preserves_extra_columns(client, auth_headers):
    content = _excel_bytes(
        [
            {
                "学号": "20230001",
                "收费时间": datetime(2026, 4, 1, 9, 0, 0),
                "收费金额": 30,
                "任意备注": "保留这一列",
            }
        ]
    )

    response = _upload(client, auth_headers, content)

    assert response.status_code == 201
    assert response.json["data"]["total_rows"] == 1
    record = ChargeRawRecord.query.one()
    assert record.source_month == "2026-04"
    assert record.parsed_charge_time == datetime(2026, 4, 1, 9, 0, 0)
    assert record.raw_data["学号"] == "20230001"
    assert record.raw_data["收费金额"] == 30
    assert record.raw_data["任意备注"] == "保留这一列"


def test_charge_raw_records_merge_by_charge_time_across_months(client, auth_headers):
    first = _excel_bytes(
        [
            {"学号": "20230003", "收费时间": datetime(2026, 5, 3, 9, 0, 0), "收费金额": 30},
            {"学号": "20230001", "收费时间": datetime(2026, 4, 1, 9, 0, 0), "收费金额": 30},
        ]
    )
    second = _excel_bytes(
        [
            {"学号": "20230002", "状态时间": datetime(2026, 4, 2, 9, 0, 0), "收费金额": 30},
        ]
    )
    assert _upload(client, auth_headers, first, "charge-may.xlsx").status_code == 201
    assert _upload(client, auth_headers, second, "charge-apr.xlsx").status_code == 201

    response = client.get("/api/v1/charge-records?page_size=10", headers=auth_headers)

    assert response.status_code == 200
    rows = response.json["data"]["items"]
    assert [row["raw_data"]["学号"] for row in rows] == ["20230001", "20230002", "20230003"]

    month_response = client.get("/api/v1/charge-records?source_month=2026-04", headers=auth_headers)
    assert month_response.status_code == 200
    assert [row["raw_data"]["学号"] for row in month_response.json["data"]["items"]] == ["20230001", "20230002"]


def test_charge_raw_import_rejects_duplicate_file_checksum(client, auth_headers):
    content = _excel_bytes([{"学号": "20230001", "收费时间": datetime(2026, 4, 1, 9, 0, 0)}])

    first = _upload(client, auth_headers, content)
    duplicate = _upload(client, auth_headers, content)

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json["details"][0]["import_job_id"] == first.json["data"]["job_id"]
    assert ChargeRawRecord.query.count() == 1


def test_charge_raw_import_rejects_missing_time_column(client, auth_headers):
    content = _excel_bytes([{"学号": "20230001", "收费金额": 30}])

    response = _upload(client, auth_headers, content)

    assert response.status_code == 422
    assert "缺少收费时间列" in response.json["message"]
    assert ChargeRawRecord.query.count() == 0


def test_charge_raw_import_keeps_invalid_time_rows_at_end(client, auth_headers):
    content = _excel_bytes(
        [
            {"学号": "invalid", "收费时间": "不是时间", "收费金额": 30},
            {"学号": "valid", "收费时间": datetime(2026, 4, 1, 9, 0, 0), "收费金额": 30},
        ]
    )

    response = _upload(client, auth_headers, content)
    query_response = client.get("/api/v1/charge-records?page_size=10", headers=auth_headers)

    assert response.status_code == 201
    assert response.json["data"]["status"] == "partial_success"
    assert response.json["data"]["invalid_time_rows"] == 1
    rows = query_response.json["data"]["items"]
    assert [row["raw_data"]["学号"] for row in rows] == ["valid", "invalid"]
    assert rows[-1]["parsed_charge_time"] is None


def test_charge_raw_export_creates_job_with_metadata_and_raw_columns(client, auth_headers):
    content = _excel_bytes(
        [
            {
                "学号": "20230001",
                "收费时间": datetime(2026, 4, 1, 9, 0, 0),
                "收费金额": 30,
                "额外列": "raw",
            }
        ]
    )
    _upload(client, auth_headers, content)

    response = client.post(
        "/api/v1/charge-records/export",
        headers=auth_headers,
        json={"source_month": "2026-04"},
    )

    assert response.status_code == 201
    export_job = db.session.get(ExportJob, response.json["data"]["export_job"]["id"])
    dataframe = pd.read_excel(export_job.stored_path)
    assert list(dataframe.columns) == [
        "导入任务ID",
        "源文件",
        "行号",
        "工作表",
        "来源月份",
        "解析收费时间",
        "原始时间值",
        "学号",
        "收费时间",
        "收费金额",
        "额外列",
    ]
    assert str(dataframe.iloc[0]["学号"]) == "20230001"
    assert dataframe.iloc[0]["额外列"] == "raw"


def test_charge_preview_automatically_archives_raw_records(client, auth_headers):
    response = client.post(
        "/api/v1/charge-batches/preview",
        headers=auth_headers,
        data={
            "file": (
                excel_file(
                    [
                        {
                            "用户账号": "20239901",
                            "收费时间": datetime(2026, 4, 2, 9, 0, 0),
                            "费用类型": "包月套餐",
                            "收费金额（元）": 30,
                            "后台归档列": "自动保留",
                        }
                    ]
                ),
                "charge-auto.xlsx",
            )
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    record = ChargeRawRecord.query.one()
    assert record.source_month == "2026-04"
    assert record.raw_data["用户账号"] == "20239901"
    assert record.raw_data["后台归档列"] == "自动保留"
