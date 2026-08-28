"""用户注册与审批接口（阶段三 T3-1）。

worker 补充完善注册资料后进入待审批；admin 对待审批用户执行通过/驳回。
审批/封禁独立：审批通过后才可接单，封禁期间无法领取/提交任务。
"""
from flask import Blueprint, g, request
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from ..auth import login_required, require_role
from ..extensions import db
from ..models import User

bp = Blueprint("users", __name__)


def _public_user(user):
    return {
        "id": user.id,
        "openid": user.openid,
        "phone": user.phone,
        "real_name": user.real_name,
        "avatar": user.avatar,
        "nickname": user.nickname,
        "role": user.role,
        "approval_status": user.approval_status,
        "status": user.status,
        "inviter_openid": user.inviter_openid,
        "bank_info": user.bank_info,
    }


@bp.post("/register")
@login_required
def register():
    """兼职用户完善注册资料，进入待审批（pending）。"""
    body = request.get_json(silent=True) or {}
    phone = (body.get("phone") or "").strip()
    real_name = (body.get("real_name") or "").strip()
    if not phone or not real_name:
        return {"code": 400, "message": "手机号与真实姓名必填"}, 400

    user = g.user
    if user.approval_status == "approved":
        return {"code": 400, "message": "已审批通过，不可重复注册"}, 400

    user.phone = phone
    user.real_name = real_name
    nickname = (body.get("nickname") or "").strip()
    if nickname:
        user.nickname = nickname
    avatar = (body.get("avatar") or "").strip()
    if avatar:
        user.avatar = avatar
    bank_info = body.get("bank_info")
    if isinstance(bank_info, dict):
        user.bank_info = bank_info
    inviter = (body.get("inviter_openid") or "").strip()
    if inviter:
        user.inviter_openid = inviter
    user.approval_status = "pending"

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return {"code": 409, "message": "手机号已注册"}, 409
    return {"code": 0, "data": _public_user(user)}


@bp.get("/pending")
@require_role("admin")
def pending_users():
    """管理端：列出待审批用户。"""
    rows = db.session.execute(
        db.select(User)
        .where(User.approval_status == "pending")
        .order_by(User.id.desc())
    ).scalars()
    return {"code": 0, "data": [_public_user(u) for u in rows]}


def _set_approval(user_id, decision):
    user = db.session.get(User, user_id)
    if not user:
        return {"code": 404, "message": "用户不存在"}, 404
    if user.approval_status == "approved":
        return {"code": 400, "message": "该用户已审批通过"}, 400
    user.approval_status = decision
    db.session.commit()
    return {"code": 0, "data": _public_user(user)}


@bp.post("/<int:user_id>/approve")
@require_role("admin")
def approve(user_id):
    """审批通过。"""
    return _set_approval(user_id, "approved")


@bp.post("/<int:user_id>/reject")
@require_role("admin")
def reject(user_id):
    """审批驳回。"""
    return _set_approval(user_id, "rejected")


@bp.get("")
@require_role("admin")
def list_users():
    """管理端：用户列表，可按审批状态/账号状态/关键字过滤（T5-2）。"""
    status = (request.args.get("status") or "").strip()
    approval = (request.args.get("approval_status") or "").strip()
    keyword = (request.args.get("keyword") or "").strip()
    q = db.select(User)
    if status in ("active", "blocked"):
        q = q.where(User.status == status)
    if approval in ("pending", "approved", "rejected"):
        q = q.where(User.approval_status == approval)
    if keyword:
        like = f"%{keyword}%"
        q = q.where(
            or_(
                User.real_name.like(like),
                User.phone.like(like),
                User.nickname.like(like),
            )
        )
    q = q.order_by(User.id.desc())
    rows = db.session.execute(q).scalars()
    return {"code": 0, "data": [_public_user(u) for u in rows]}


def _set_user_status(user_id, status):
    user = db.session.get(User, user_id)
    if not user:
        return {"code": 404, "message": "用户不存在"}, 404
    user.status = status
    db.session.commit()
    return {"code": 0, "data": _public_user(user)}


@bp.post("/<int:user_id>/block")
@require_role("admin")
def block_user(user_id):
    """封禁用户（独立于审批，T5-2 / T5-6 联动）。"""
    return _set_user_status(user_id, "blocked")


@bp.post("/<int:user_id>/unblock")
@require_role("admin")
def unblock_user(user_id):
    """解封用户。"""
    return _set_user_status(user_id, "active")