"""健康检查，验证服务与数据库连通。"""
from flask import Blueprint

from ..extensions import db

bp = Blueprint("health", __name__)


@bp.get("/ping")
def ping():
    return {"code": 0, "message": "pong", "data": {"status": "ok"}}


@bp.get("/db")
def db_check():
    try:
        db.session.execute(db.text("SELECT 1"))
        return {"code": 0, "message": "db ok"}
    except Exception as exc:  # noqa: BLE001
        return {"code": 500, "message": "db error", "detail": str(exc)}, 500