from __future__ import annotations

from collections.abc import Iterable

from ..extensions import db
from ..models import SystemConfig


DEFAULT_CONFIGS = {
    "system.timezone": {"value": "Asia/Shanghai", "remark": "系统时区"},
    "charge.last_processed_charge_time": {"value": None, "remark": "收费增量水位"},
    "package.month_days": {"value": 31, "remark": "包月天数"},
    "package.year_days": {"value": 365, "remark": "包年天数"},
    "batch.warn_days_default": {"value": 1, "remark": "批次默认预警天数"},
    "inventory.low_stock_threshold": {"value": 50, "remark": "库存低水位阈值"},
    "charge.max_execute_rows": {"value": 20, "remark": "单次收费执行最大行数"},
    "full_list.sheet_name": {"value": "Sheet1", "remark": "完整名单默认工作表"},
    "storage.cleanup_days": {"value": 7, "remark": "临时文件保留天数"},
}


def set_system_defaults() -> None:
    for key, item in DEFAULT_CONFIGS.items():
        existing = db.session.get(SystemConfig, key)
        if existing is None:
            db.session.add(
                SystemConfig(
                    config_key=key,
                    config_value={"value": item["value"]},
                    remark=item.get("remark"),
                )
            )
    db.session.commit()


def get_config_value(key: str, default=None):
    item = db.session.get(SystemConfig, key)
    if item is None:
        return default
    return item.config_value.get("value", default)


def update_configs(payload: dict) -> None:
    for key, value in payload.items():
        set_config_value(key, value, commit=False)
    db.session.commit()


def set_config_value(key: str, value, commit: bool = True) -> SystemConfig:
    item = db.session.get(SystemConfig, key)
    if item is None:
        default_remark = DEFAULT_CONFIGS.get(key, {}).get("remark")
        item = SystemConfig(config_key=key, config_value={"value": value}, remark=default_remark)
        db.session.add(item)
    else:
        item.config_value = {"value": value}
    if commit:
        db.session.commit()
    return item


def serialize_configs(keys: Iterable[str] | None = None) -> dict[str, dict]:
    query = SystemConfig.query.order_by(SystemConfig.config_key.asc())
    if keys is not None:
        query = query.filter(SystemConfig.config_key.in_(list(keys)))
    return {
        item.config_key: {
            "value": item.config_value.get("value"),
            "remark": item.remark,
        }
        for item in query.all()
    }
