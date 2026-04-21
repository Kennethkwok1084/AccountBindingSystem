from __future__ import annotations

from pathlib import Path


def ensure_storage_dirs(storage_root: str) -> None:
    base = Path(storage_root)
    for name in ("uploads", "exports", "tmp"):
        (base / name).mkdir(parents=True, exist_ok=True)

