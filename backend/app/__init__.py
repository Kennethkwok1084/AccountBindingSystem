from flask import Flask

from .blueprints import register_blueprints
from .cli import register_cli
from .config import Config
from .extensions import db, migrate
from .middleware import register_middleware
from .models import load_models  # noqa: F401
from .services.bootstrap import ensure_storage_dirs


def create_app(config_object: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    ensure_storage_dirs(app.config["STORAGE_ROOT"])

    db.init_app(app)
    migrate.init_app(app, db, directory="migrations")

    register_middleware(app)
    register_blueprints(app)
    register_cli(app)

    return app
