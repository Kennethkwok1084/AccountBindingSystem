"""Simple cron loop for the auditor container. Runs main.run_audit() on schedule."""
from __future__ import annotations

import os
import sys
import time
import traceback
from datetime import date

from croniter import croniter


def _next_fire(cron_expr: str) -> float:
    import datetime as dt
    now = dt.datetime.now()
    return croniter(cron_expr, now).get_next(float)


def main():
    cron_expr = os.environ.get("AUDIT_RUN_CRON", "0 2 * * *")
    print(f"[cron_runner] starting, schedule: {cron_expr}")

    # Support one-shot mode: pass --run-now to trigger immediately then exit
    if "--run-now" in sys.argv:
        from main import run_audit
        run_audit()
        return

    while True:
        next_fire = _next_fire(cron_expr)
        sleep_secs = max(0, next_fire - time.time())
        print(f"[cron_runner] next audit in {sleep_secs/3600:.1f}h")
        time.sleep(sleep_secs)
        try:
            from main import run_audit
            run_audit(date.today())
        except Exception:  # noqa: BLE001
            print("[cron_runner] audit run failed", file=sys.stderr)
            traceback.print_exc()


if __name__ == "__main__":
    main()
