"""违规与黑名单管理接口（阶段五 T5-6，不依赖阶段四）。

记录违规并可选联动封禁：punish_level=block 时同时将用户 status 置为 blocked。
"""
from flask import Blueprint, g, request

from ..auth import require_role
from ..extensions import db
from ..models import User, Violation

bp = Blueprint("violations", __name__)

VALID_TYPE = {"alter_original", "edit_jitter", "submit_irrelevant", "other"}
VALID_PUNISH = {"warning", "suspend", "block"}


def _public_vio(v):
    return {
        "id": v.id,
        "openid": v.openid,
        "user_name": v.user_name,
        "type": v.type,
        "punish_level": v.punish_level,
        "reason": v.reason,
        "operator_id": v.operator_id,
        "create_time": v.create_time.isoformat() if v.create_time else None,
    }


@bp.post("")
@require_role("admin")
def create_violation():
    """记录违规；punish_level=block 时联动封禁用户。

    body: { openid, type, punish_level, reason? }
    """
    body = request.get_json(silent=True) or {}
    openid = (body.get("openid") or "").strip()
    v_type = (body.get("type") or "").strip()
    punish = (body.get("punish_level") or "").strip()
    reason = (body.get("reason") or "").strip()

    if not openid:
        return {"code": 400, "message": "openid 必填"}, 400
    if v_type not in VALID_TYPE:
        return {"code": 400, "message": "type 无效"}, 400
    if punish not in VALID_PUNISH:
        return {"code": 400, "message": "punish_level 无效"}, 400

    user = db.session.execute(
        db.select(User).where(User.openid == openid)
    ).scalar_one_or_none()
    if not user:
        return {"code": 404, "message": "用户不存在"}, 404

    vio = Violation(
        openid=openid,
        user_name=user.real_name,
        type=v_type,
        punish_level=punish,
        reason=reason or None,
        operator_id=g.user.id,
    )
    db.session.add(vio)
    # 黑名单联动：block 级处罚直接封禁账号
    if punish == "block":
        user.status = "blocked"
    db.session.commit()
    return {"code": 0, "data": _public_vio(vio)}


@bp.get("")
@require_role("admin")
def list_violations():
    """管理端：违规记录列表，可按 openid 过滤。"""
    openid = (request.args.get("openid") or "").strip()
    q = db.select(Violation)
    if openid:
        q = q.where(Violation.openid == openid)
    q = q.order_by(Violation.id.desc())
    rows = db.session.execute(q).scalars()
    return {"code": 0, "data": [_public_vio(v) for v in rows]}