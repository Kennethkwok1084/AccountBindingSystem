from __future__ import annotations

import time

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask

from .services.scheduler_service import JOB_RUNNERS


def run_scheduler(app: Flask) -> None:
    scheduler = BackgroundScheduler(timezone=app.config["SYSTEM_TIMEZONE"])
    scheduler.add_job(lambda: _run(app, "batch_expire_warning"), "cron", hour=0, minute=5, id="batch_expire_warning", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(lambda: _run(app, "binding_expire_release"), "cron", hour=0, minute=10, id="binding_expire_release", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(lambda: _run(app, "inventory_alert_scan"), "cron", hour=0, minute=15, id="inventory_alert_scan", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(lambda: _run(app, "cleanup_temp_files"), "cron", hour=0, minute=20, id="cleanup_temp_files", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.start()
    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        scheduler.shutdown()


def _run(app: Flask, job_name: str) -> None:
    with app.app_context():
        JOB_RUNNERS[job_name]()
