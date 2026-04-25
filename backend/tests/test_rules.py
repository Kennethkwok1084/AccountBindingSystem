import pandas as pd

from datetime import datetime

from app.services import date_service
from app.services.date_service import compute_expire_from, package_days
from app.services.storage_service import (
    create_charge_execution_export_file,
    create_export_file,
    create_tabular_export_file,
)


def test_package_days_month():
    assert package_days("30元移动包月75M") == 31


def test_package_days_year():
    assert package_days("包年套餐") == 365


def test_compute_expire_from():
    from datetime import date

    assert compute_expire_from(date(2026, 4, 20), "包月套餐").isoformat() == "2026-05-21"


def test_export_file_names_do_not_collide(app):
    filename1, path1 = create_export_file([{"学号": "1", "移动账户": "yd001"}])
    filename2, path2 = create_export_file([{"学号": "2", "移动账户": "yd002"}])

    assert filename1 != filename2
    assert filename1.endswith(".xlsx")
    assert filename2.endswith(".xlsx")

    rows1 = pd.read_excel(path1).to_dict(orient="records")
    rows2 = pd.read_excel(path2).to_dict(orient="records")
    assert rows1[0]["学号"] == 1
    assert rows2[0]["学号"] == 2


def test_charge_execution_export_uses_xls_suffix_and_account_header(app):
    filename, path = create_charge_execution_export_file([{"学号": "2023001001", "移动账户": "yd001"}])

    assert filename.endswith(".xls")
    assert open(path, "rb").read(8) == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

    dataframe = pd.read_excel(path)
    assert list(dataframe.columns)[:2] == ["账号", "移动账户"]
    assert "学号" not in dataframe.columns
    assert dataframe.iloc[0]["账号"] == 2023001001


def test_tabular_export_file_defaults_to_xlsx(app):
    filename, path = create_tabular_export_file([{"学号": "2023001001"}], "台账", ["学号"])

    assert filename.endswith(".xlsx")
    rows = pd.read_excel(path).to_dict(orient="records")
    assert rows[0]["学号"] == 2023001001


def test_localnow_uses_system_timezone(monkeypatch):
    monkeypatch.setattr(date_service, "utcnow", lambda: datetime(2026, 4, 21, 1, 9, 0))
    assert date_service.localnow().strftime("%Y-%m-%d %H:%M:%S") == "2026-04-21 09:09:00"
