from __future__ import annotations

from collections.abc import Iterable

from ..extensions import db
from ..models import SystemConfig


DEFAULT_CONFIGS = {
    "system.timezone": {"value": "Asia/Shanghai", "remark": "系统时区", "label": "系统时区", "type": "text", "group": "基础设置"},
    "charge.last_processed_charge_time": {"value": None, "remark": "收费增量水位", "label": "收费增量水位", "type": "text", "group": "收费设置"},
    "package.month_days": {"value": 31, "remark": "包月天数", "label": "包月天数", "type": "number", "group": "套餐规则"},
    "package.year_days": {"value": 365, "remark": "包年天数", "label": "包年天数", "type": "number", "group": "套餐规则"},
    "batch.warn_days_default": {"value": 1, "remark": "批次默认预警天数", "label": "批次默认预警天数", "type": "number", "group": "批次设置"},
    "inventory.low_stock_threshold": {"value": 50, "remark": "库存低水位阈值", "label": "库存低水位阈值", "type": "number", "group": "库存预警"},
    "charge.max_execute_rows": {"value": 0, "remark": "单次收费执行最大行数（0 表示不限制）", "label": "收费单次最大执行行数", "type": "number", "group": "收费设置"},
    "full_list.sheet_name": {"value": "Sheet1", "remark": "完整名单默认工作表", "label": "完整名单默认工作表", "type": "text", "group": "导入设置"},
    "storage.cleanup_days": {"value": 7, "remark": "临时文件保留天数", "label": "临时文件保留天数", "type": "number", "group": "存储清理"},
    "integration.syslog.enabled": {"value": False, "remark": "开启后将审计日志转发到 Syslog", "label": "启用 Syslog 转发", "type": "boolean", "group": "日志集成"},
    "integration.syslog.host": {"value": "", "remark": "Syslog 服务器地址", "label": "Syslog 主机", "type": "text", "group": "日志集成"},
    "integration.syslog.port": {"value": 514, "remark": "Syslog 服务器端口", "label": "Syslog 端口", "type": "number", "group": "日志集成"},
    "integration.syslog.protocol": {"value": "udp", "remark": "推荐先使用 UDP", "label": "Syslog 协议", "type": "select", "group": "日志集成", "options": [
        {"label": "UDP", "value": "udp"},
        {"label": "TCP", "value": "tcp"},
    ]},
    "integration.syslog.facility": {"value": "user", "remark": "Syslog facility 名称", "label": "Syslog Facility", "type": "select", "group": "日志集成", "options": [
        {"label": "user", "value": "user"},
        {"label": "local0", "value": "local0"},
        {"label": "local1", "value": "local1"},
        {"label": "local2", "value": "local2"},
        {"label": "local3", "value": "local3"},
        {"label": "local4", "value": "local4"},
        {"label": "local5", "value": "local5"},
        {"label": "local6", "value": "local6"},
        {"label": "local7", "value": "local7"},
    ]},
    "integration.syslog.app_name": {"value": "account-bind-system", "remark": "转发到 Syslog 时使用的应用名", "label": "Syslog 应用名", "type": "text", "group": "日志集成"},
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
            "label": DEFAULT_CONFIGS.get(item.config_key, {}).get("label", item.config_key),
            "type": DEFAULT_CONFIGS.get(item.config_key, {}).get("type", "text"),
            "group": DEFAULT_CONFIGS.get(item.config_key, {}).get("group", "其他"),
            "options": DEFAULT_CONFIGS.get(item.config_key, {}).get("options", []),
        }
        for item in query.all()
    }
