from __future__ import annotations

import click
from flask import Flask
from flask_migrate import current, upgrade

from .extensions import db
from .models import AdminUser
from .security import hash_password
from .services.bootstrap import ensure_storage_dirs
from .services.config_service import set_system_defaults


def register_cli(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db_command() -> None:
        ensure_storage_dirs(app.config["STORAGE_ROOT"])
        upgrade(directory="migrations")
        set_system_defaults()
        click.echo("database migrated and defaults initialized")

    @app.cli.command("db-version")
    def db_version_command() -> None:
        current(directory="migrations")

    @app.cli.command("seed-admin")
    @click.option("--username", default=None)
    @click.option("--password", default=None)
    def seed_admin_command(username: str | None, password: str | None) -> None:
        username = username or app.config["DEFAULT_ADMIN_USERNAME"]
        password = password or app.config["DEFAULT_ADMIN_PASSWORD"]
        if not password:
            raise click.ClickException("缺少管理员初始密码，请通过环境变量 DEFAULT_ADMIN_PASSWORD 或 --password 提供")

        existing = AdminUser.query.filter_by(username=username).first()
        if existing:
            click.echo("admin already exists")
            return

        admin = AdminUser(username=username, password_hash=hash_password(password))
        db.session.add(admin)
        db.session.commit()
        click.echo(f"admin {username} created")
