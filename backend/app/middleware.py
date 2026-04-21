from __future__ import annotations

import uuid

from flask import Flask, g, request


def register_middleware(app: Flask) -> None:
    @app.before_request
    def attach_request_context() -> None:
        g.request_id = request.headers.get("X-Request-Id") or f"req_{uuid.uuid4().hex[:12]}"

