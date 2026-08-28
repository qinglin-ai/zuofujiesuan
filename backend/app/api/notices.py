"""公告 / 流程 / 项目动态 / FAQ 接口（阶段五 T5-7，不依赖阶段四）。"""
from flask import Blueprint, g, request

from ..auth import login_required, require_role
from ..extensions import db
from ..models import Notice

bp = Blueprint("notices", __name__)

VALID_TARGET = {"all", "worker", "admin", "skill"}
VALID_TYPE = {"notice", "flow", "project", "faq"}


def _public_notice(n):
    return {
        "id": n.id,
        "title": n.title,
        "content": n.content,
        "target": n.target,
        "type": n.type,
        "create_time": n.create_time.isoformat() if n.create_time else None,
    }


@bp.post("")
@require_role("admin")
def create_notice():
    """管理端：发布公告。body: { title, content, target?, type? }"""
    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "").strip()
    content = (body.get("content") or "").strip()
    if not title or not content:
        return {"code": 400, "message": "标题与内容必填"}, 400
    target = (body.get("target") or "all").strip()
    if target not in VALID_TARGET:
        return {"code": 400, "message": "target 无效"}, 400
    n_type = (body.get("type") or "notice").strip()
    if n_type not in VALID_TYPE:
        return {"code": 400, "message": "type 无效"}, 400

    n = Notice(title=title, content=content, target=target, type=n_type)
    db.session.add(n)
    db.session.commit()
    return {"code": 0, "data": _public_notice(n)}


@bp.get("")
@login_required
def list_notices():
    """按角色可见性返回公告列表。"""
    role = getattr(g, "role", None)
    q = db.select(Notice)
    if role == "admin":
        q = q.where(Notice.target.in_(["all", "admin"]))
    else:
        q = q.where(Notice.target.in_(["all", "worker"]))
    q = q.order_by(Notice.id.desc())
    rows = db.session.execute(q).scalars()
    return {"code": 0, "data": [_public_notice(n) for n in rows]}