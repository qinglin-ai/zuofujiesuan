"""鉴权辅助模块（JWT 编解码、微信登录、角色校验装饰器）。"""
from datetime import datetime, timedelta
from functools import wraps

import jwt
from flask import current_app, g, request
from jwt import PyJWTError

from ..models import User
from ..extensions import db


def _jwt_secret():
    return current_app.config["JWT_SECRET"]


def create_token(openid, role):
    """签发 JWT。"""
    payload = {
        "sub": openid,
        "role": role,
        "exp": datetime.utcnow()
        + timedelta(hours=current_app.config["JWT_EXPIRE_HOURS"]),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=current_app.config["JWT_ALGORITHM"])


def decode_token(token):
    """解码并校验 JWT，失败抛异常。"""
    return jwt.decode(token, _jwt_secret(), algorithms=[current_app.config["JWT_ALGORITHM"]])


def login_required(fn):
    """要求有效登录态，注入 g.openid / g.role。"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        scheme, _, token = auth.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return {"code": 401, "message": "未登录"}, 401
        try:
            payload = decode_token(token)
        except PyJWTError:
            return {"code": 401, "message": "登录已失效"}, 401
        user = db.session.get(User, None) or db.session.execute(
            db.select(User).where(User.openid == payload["sub"])
        ).scalar_one_or_none()
        if not user or user.status != "active":
            return {"code": 403, "message": "账号不可用"}, 403
        g.openid = payload["sub"]
        g.role = payload["role"]
        g.user = user
        return fn(*args, **kwargs)
    return wrapper


def require_role(role):
    """要求指定角色的接口装饰器（依赖 login_required 先行）。"""
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            if g.role != role:
                return {"code": 403, "message": "无权限"}, 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def wechat_code_to_openid(code):
    """调用微信 code2session 换取 openid（未配置时返回占位值以便本地联调）。"""
    appid = current_app.config.get("WX_APPID", "")
    secret = current_app.config.get("WX_SECRET", "")
    if not appid or not secret:
        # 未注册占位：本地开发直接用 code 作为 openid 前缀，便于链路跑通
        return f"dev_openid_{code[:16]}"
    import requests
    resp = requests.get(
        "https://api.weixin.qq.com/sns/jscode2session",
        params={"appid": appid, "secret": secret, "js_code": code, "grant_type": "authorization_code"},
        timeout=5,
    )
    data = resp.json()
    if data.get("errcode"):
        raise ValueError(f"code2session 失败: {data}")
    return data["openid"]