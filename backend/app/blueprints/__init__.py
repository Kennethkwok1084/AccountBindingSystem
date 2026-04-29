from flask import Blueprint

from .accounts import bp as accounts_bp
from .alerts import bp as alerts_bp
from .audit import bp as audit_bp
from .auth import bp as auth_bp
from .charge_records import bp as charge_records_bp
from .config import bp as config_bp
from .dashboard import bp as dashboard_bp
from .exports import bp as exports_bp
from .operations import bp as operations_bp
from .scheduler import bp as scheduler_bp
from .students import bp as students_bp


def register_blueprints(app):
    api = Blueprint("api", __name__, url_prefix="/api/v1")
    for blueprint in (
        auth_bp,
        config_bp,
        dashboard_bp,
        accounts_bp,
        charge_records_bp,
        operations_bp,
        students_bp,
        exports_bp,
        alerts_bp,
        scheduler_bp,
        audit_bp,
    ):
        api.register_blueprint(blueprint)
    app.register_blueprint(api)
