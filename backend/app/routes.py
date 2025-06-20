from flask import Blueprint

bp = Blueprint("api", __name__)


@bp.route("/ping")
def ping():
    return {"message": "pong"}
