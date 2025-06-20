from datetime import datetime

from . import db


class Account(db.Model):
    __tablename__ = "accounts"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    is_bound = db.Column(db.Boolean, default=False)
    student_id = db.Column(db.String(32))
    bind_time = db.Column(db.DateTime)
    create_time = db.Column(db.DateTime, default=datetime.utcnow)


class BindingLog(db.Model):
    __tablename__ = "binding_logs"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), nullable=False)
    student_id = db.Column(db.String(32))
    bind_time = db.Column(db.DateTime, default=datetime.utcnow)
    operator = db.Column(db.String(64), default="system")
    action = db.Column(db.String(32))
