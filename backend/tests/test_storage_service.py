from __future__ import annotations

from io import BytesIO

import pytest
from werkzeug.datastructures import FileStorage

from app.services.storage_service import save_upload


def test_save_upload_accepts_xls(app):
    with app.app_context():
        file = FileStorage(stream=BytesIO(b"fake-xls-content"), filename="accounts.xls")
        stored_path, checksum = save_upload(file, "account_pool")
        assert stored_path.endswith(".xls")
        assert len(checksum) == 64


def test_save_upload_rejects_non_excel_suffix(app):
    with app.app_context():
        file = FileStorage(stream=BytesIO(b"not-excel"), filename="accounts.txt")
        with pytest.raises(ValueError, match="仅支持上传 \\.xlsx 或 \\.xls 文件"):
            save_upload(file, "account_pool")
