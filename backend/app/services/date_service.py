from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from flask import has_app_context

from .config_service import get_config_value


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def package_days(package_name: str | None) -> int:
    name = (package_name or "").lower()
    if "年" in name:
        return _config_int("package.year_days", 365)
    return _config_int("package.month_days", 31)


def normalize_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return datetime.fromisoformat(str(value)).date()


def normalize_datetime(value) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    return datetime.fromisoformat(str(value)).replace(tzinfo=None)


def compute_expire_from(base_date: date, package_name: str | None) -> date:
    return base_date + timedelta(days=package_days(package_name))


def _config_int(key: str, default: int) -> int:
    if not has_app_context():
        return default
    value = get_config_value(key, default)
    return int(value if value is not None else default)
