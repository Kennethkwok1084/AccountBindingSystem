import pandas as pd

from app.services.date_service import compute_expire_from, package_days
from app.services.storage_service import create_export_file


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

    rows1 = pd.read_excel(path1).to_dict(orient="records")
    rows2 = pd.read_excel(path2).to_dict(orient="records")
    assert rows1[0]["学号"] == 1
    assert rows2[0]["学号"] == 2
