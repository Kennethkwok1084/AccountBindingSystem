import pymysql
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os

# 将PyMySQL注册为MySQLdb的替代品
pymysql.install_as_MySQLdb()

db = SQLAlchemy()


def create_app() -> Flask:
    """Application factory."""
    app = Flask(__name__)
    app.config.from_object("config.Config")
    uri = os.getenv("SQLALCHEMY_DATABASE_URI")
    if uri:
        app.config["SQLALCHEMY_DATABASE_URI"] = uri
    db.init_app(app)

    with app.app_context():
        from . import routes

        app.register_blueprint(routes.bp)
        db.create_all()

    return app
