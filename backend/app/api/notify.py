"""微信支付异步回调通知（商家转账结果）。

无登录鉴权——由微信请求签名保护（Wechatpay-Signature 验签 + Wechatpay-Serial 公钥ID比对）。
地址：POST /api/pay/transfer/notify（须为公网 HTTPS 可访问）。
"""
import json

from flask import Blueprint, current_app, jsonify, request

from .. import wxpay
from .wallet import handle_transfer_event

bp = Blueprint("wxpay_notify", __name__, url_prefix="/api/pay")


@bp.post("/transfer/notify")
def transfer_notify():
    raw = request.get_data()
    client = wxpay.get_client(current_app)
    if client is None:
        current_app.logger.warning("收到微信回调但未启用微信支付配置")
        return jsonify({"code": "FAIL", "message": "未配置"}), 500

    if not client.verify_notify(request.headers, raw):
        current_app.logger.warning("微信回调验签失败")
        return jsonify({"code": "FAIL", "message": "验签失败"}), 401

    try:
        body = json.loads(raw.decode("utf-8") or "{}")
    except ValueError:
        return jsonify({"code": "FAIL", "message": "报文非法"}), 400

    resource = body.get("resource")
    if not resource:
        return jsonify({"code": "FAIL", "message": "缺少 resource"}), 400
    try:
        event = client.decrypt_notify_resource(resource)
    except Exception:
        current_app.logger.exception("微信回调 resource 解密失败")
        return jsonify({"code": "FAIL", "message": "解密失败"}), 500

    out_bill_no = event.get("out_bill_no") or ""
    if not out_bill_no:
        return jsonify({"code": "FAIL", "message": "缺少单号"}), 400

    # 幂等 + 陈旧回调忽略由 handle_transfer_event 处理；查不到记录也返回成功，停止微信重推
    handle_transfer_event(out_bill_no, event)
    return jsonify({"code": "SUCCESS", "message": "成功"})
