from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from werkzeug.datastructures import FileStorage

from app.services import storage_service
from app.services.storage_service import save_upload
from .conftest import excel_file


def test_save_upload_accepts_xls(app, monkeypatch):
    monkeypatch.setattr(storage_service, "localnow", lambda: datetime(2026, 4, 20, 9, 30, 0))
    with app.app_context():
        file = FileStorage(stream=BytesIO(b"fake-xls-content"), filename="accounts.xls")
        stored_path, checksum = save_upload(file, "account_pool")
        assert stored_path.endswith(".xls")
        assert Path(stored_path).parts[-3:-1] == ("2026-04", "account_pool")
        assert len(checksum) == 64


def test_save_upload_rejects_non_excel_suffix(app):
    with app.app_context():
        file = FileStorage(stream=BytesIO(b"not-excel"), filename="accounts.txt")
        with pytest.raises(ValueError, match="仅支持上传 \\.xlsx 或 \\.xls 文件"):
            save_upload(file, "account_pool")


def test_upload_archives_list_and_download(client, auth_headers):
    response = client.post(
        "/api/v1/mobile-accounts/import",
        headers=auth_headers,
        data={"file": (excel_file([{"account": "yd-archive-001", "batch_code": "202604"}]), "accounts.xlsx")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 201

    response = client.get("/api/v1/upload-archives")
    assert response.status_code == 200
    items = response.json["data"]["items"]
    assert len(items) == 1
    assert items[0]["file_count"] == 1
    assert items[0]["categories"] == [{"count": 1, "job_type": "account_pool", "label": "账号池"}]

    response = client.get(f"/api/v1/upload-archives/{items[0]['month']}/download")
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("application/zip")
    with ZipFile(BytesIO(response.data)) as archive:
        names = archive.namelist()
    assert len(names) == 1
    assert names[0].endswith("/1_accounts.xlsx")
