from __future__ import annotations

import json
import logging
from logging.handlers import SysLogHandler
import socket

from flask import current_app, has_app_context

from .config_service import get_config_value


FACILITY_MAP = {
    "user": SysLogHandler.LOG_USER,
    "local0": SysLogHandler.LOG_LOCAL0,
    "local1": SysLogHandler.LOG_LOCAL1,
    "local2": SysLogHandler.LOG_LOCAL2,
    "local3": SysLogHandler.LOG_LOCAL3,
    "local4": SysLogHandler.LOG_LOCAL4,
    "local5": SysLogHandler.LOG_LOCAL5,
    "local6": SysLogHandler.LOG_LOCAL6,
    "local7": SysLogHandler.LOG_LOCAL7,
}


def _get_syslog_config(overrides: dict | None = None, *, require_enabled: bool = True) -> dict:
    overrides = overrides or {}
    enabled = bool(overrides.get("integration.syslog.enabled", get_config_value("integration.syslog.enabled", False)))
    host = str(overrides.get("integration.syslog.host", get_config_value("integration.syslog.host", "")) or "").strip()
    if require_enabled and not enabled:
        raise ValueError("Syslog 转发未启用")
    if not host:
        raise ValueError("请先填写 Syslog 主机")

    protocol = str(overrides.get("integration.syslog.protocol", get_config_value("integration.syslog.protocol", "udp")) or "udp").strip().lower()
    port = int(overrides.get("integration.syslog.port", get_config_value("integration.syslog.port", 514)) or 514)
    facility_name = str(overrides.get("integration.syslog.facility", get_config_value("integration.syslog.facility", "user")) or "user").strip().lower()
    app_name = str(overrides.get("integration.syslog.app_name", get_config_value("integration.syslog.app_name", "account-bind-system")) or "account-bind-system").strip()
    facility = FACILITY_MAP.get(facility_name, SysLogHandler.LOG_USER)
    socktype = socket.SOCK_STREAM if protocol == "tcp" else socket.SOCK_DGRAM
    return {
        "enabled": enabled,
        "host": host,
        "port": port,
        "protocol": protocol,
        "facility": facility,
        "app_name": app_name,
        "socktype": socktype,
    }


def _send_syslog(config: dict, event_type: str, payload: dict) -> None:
    logger_name = f"{config['app_name']}.syslog"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    handler = SysLogHandler(address=(config["host"], config["port"]), facility=config["facility"], socktype=config["socktype"])
    handler.setFormatter(logging.Formatter(f"{config['app_name']}: %(message)s"))
    logger.handlers = [handler]
    try:
        logger.info(json.dumps({"event_type": event_type, **payload}, ensure_ascii=False, default=str))
    finally:
        try:
            handler.close()
        finally:
            logger.handlers = []


def emit_syslog(event_type: str, payload: dict) -> None:
    if not has_app_context():
        return
    try:
        config = _get_syslog_config()
        _send_syslog(config, event_type, payload)
    except Exception as exc:  # noqa: BLE001
        current_app.logger.warning("syslog emit failed: %s", exc)


def test_syslog_connectivity(overrides: dict | None = None) -> dict:
    if not has_app_context():
        raise RuntimeError("缺少应用上下文")
    config = _get_syslog_config(overrides, require_enabled=False)
    _send_syslog(
        config,
        "syslog_connectivity_test",
        {
            "message": "syslog connectivity test from account-bind-system",
        },
    )
    return {
        "host": config["host"],
        "port": config["port"],
        "protocol": config["protocol"],
        "app_name": config["app_name"],
    }
