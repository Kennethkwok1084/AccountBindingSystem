try:
    from app import create_app
    from app.scheduler_jobs import run_scheduler
except ModuleNotFoundError:  # pragma: no cover - supports root-level imports
    from backend.app import create_app
    from backend.app.scheduler_jobs import run_scheduler


app = create_app()


if __name__ == "__main__":
    run_scheduler(app)
