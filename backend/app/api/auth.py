"""注册/登录鉴权接口。(注册审批完整逻辑在阶段三实现，此处仅打通登录链路)"""
from flask import Blueprint, request
from sqlalchemy import or_
from werkzeug.security import check_password_hash

from ..auth import create_token, login_required, wechat_code_to_openid
from ..extensions import db
from ..models import User

bp = Blueprint("auth", __name__)


def _default_user(openid):
    """登录时若用户不存在则自动建档（占位）；审批规则阶段三细化。"""
    user = db.session.execute(
        db.select(User).where(User.openid == openid)
    ).scalar_one_or_none()
    if not user:
        user = User(
            openid=openid,
            phone="",
            real_name="",
            role="worker",
            approval_status="pending",
            status="active",
        )
        db.session.add(user)
        db.session.commit()
    return user


@bp.post("/login")
def login():
    """wx.login 的 code 换 openid 并签发 JWT。"""
    body = request.get_json(silent=True) or {}
    code = (body.get("code") or "").strip()
    if not code:
        return {"code": 400, "message": "缺少 code"}, 400
    try:
        openid = wechat_code_to_openid(code)
    except ValueError as exc:
        return {"code": 401, "message": str(exc)}, 401

    user = _default_user(openid)
    token = create_token(user.openid, user.role)
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "token": token,
            "user": {
                "openid": user.openid,
                "role": user.role,
                "approval_status": user.approval_status,
                "status": user.status,
                "nickname": user.nickname,
            },
        },
    }


@bp.post("/admin/login")
def admin_login():
    """管理后台：admin 账号密码登录（T5-1），签发放大角色 JWT。

    body: { account: 手机号|真实姓名|openid, password }
    仅 role=admin 且密码匹配、账号正常时放行。
    """
    body = request.get_json(silent=True) or {}
    account = (body.get("account") or "").strip()
    password = body.get("password") or ""
    if not account or not password:
        return {"code": 400, "message": "账号与密码必填"}, 400
    user = db.session.execute(
        db.select(User).where(
            or_(
                User.phone == account,
                User.real_name == account,
                User.openid == account,
            )
        )
    ).scalar_one_or_none()
    if not user:
        return {"code": 401, "message": "账号或密码错误"}, 401
    if user.role != "admin":
        return {"code": 403, "message": "非管理员账号"}, 403
    if not user.password_hash or not check_password_hash(user.password_hash, password):
        return {"code": 401, "message": "账号或密码错误"}, 401
    if user.status != "active":
        return {"code": 403, "message": "账号已封禁"}, 403
    token = create_token(user.openid, "admin")
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "token": token,
            "user": {
                "openid": user.openid,
                "role": "admin",
                "nickname": user.nickname,
            },
        },
    }


@bp.get("/me")
@login_required
def me():
    from flask import g
    return {
        "code": 0,
        "data": {
            "openid": g.user.openid,
            "role": g.user.role,
            "approval_status": g.user.approval_status,
            "status": g.user.status,
        },
    }