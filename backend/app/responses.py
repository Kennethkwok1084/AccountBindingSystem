from __future__ import annotations

from flask import g, jsonify


def success(data=None, message: str = "ok", status: int = 200):
    return (
        jsonify(
            {
                "code": 0,
                "message": message,
                "data": data or {},
                "request_id": getattr(g, "request_id", ""),
            }
        ),
        status,
    )


def error(code: str, message: str, status: int = 400, details=None):
    return (
        jsonify(
            {
                "code": code,
                "message": message,
                "details": details or [],
                "request_id": getattr(g, "request_id", ""),
            }
        ),
        status,
    )

