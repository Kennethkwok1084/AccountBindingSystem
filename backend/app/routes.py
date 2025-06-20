from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename
from openpyxl import load_workbook
from .models import Account, BindingLog
from . import db
from .utils import add_log
from datetime import datetime

bp = Blueprint("api", __name__)


@bp.route("/ping")
def ping():
    return {"message": "pong"}


@bp.route("/accounts/import", methods=["POST"])
def import_accounts():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "no file"}), 400

    filename = secure_filename(file.filename)
    wb = load_workbook(file)
    ws = wb.active
    imported = 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        username, password = row[:2]
        if not username or not password:
            continue
        if not Account.query.filter_by(username=username).first():
            account = Account(username=username, password=password)
            db.session.add(account)
            imported += 1
    db.session.commit()
    return jsonify({"imported": imported})


@bp.route("/accounts/bind", methods=["POST"])
def bind_account():
    data = request.get_json() or {}
    username = data.get("username")
    student_id = data.get("student_id")
    if not username or not student_id:
        return jsonify({"error": "missing data"}), 400
    account = Account.query.filter_by(username=username).first()
    if not account:
        return jsonify({"error": "account not found"}), 404
    if account.is_bound:
        return jsonify({"error": "already bound"}), 400
    account.is_bound = True
    account.student_id = student_id
    account.bind_time = datetime.utcnow()
    db.session.add(account)
    db.session.commit()
    add_log(username, student_id, "bind")
    return jsonify({"status": "ok"})


@bp.route("/accounts", methods=["GET"])
def list_accounts():
    accounts = Account.query.all()
    data = [
        {
            "username": a.username,
            "is_bound": a.is_bound,
            "student_id": a.student_id,
            "bind_time": a.bind_time.isoformat() if a.bind_time else None,
        }
        for a in accounts
    ]
    return jsonify(data)
