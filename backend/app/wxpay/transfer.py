"""商家转账 payload 构建与错误码分类（官方防重决策表）。

防重铁律（微信官方文档 2025.03.21）：
遇到 ALREADY_EXISTS / FREQUENCY_LIMIT_* / SYSTEM_ERROR 等错误码时，
必须先通过查单接口确认原单状态；只有当查单结果明确为 FAIL 时，
才允许生成新的 out_bill_no 重试。否则会有重复转账的资金风险。
"""
from decimal import Decimal

# 结果未知，必须先查单，绝不能立即换单
QUERY_FIRST_CODES = {
    "ALREADY_EXISTS",
    "SYSTEM_ERROR",
    "FREQUENCY_LIMIT_EXCEED",
    "FREQUENCY_LIMIT",
    "RATELIMIT_EXCEEDED",
}

# 确定性失败，换单也必失败，直接转人工
FINAL_FAIL_CODES = {
    "PARAM_ERROR",
    "INVALID_REQUEST",
    "NO_AUTH",
    "SIGN_ERROR",
    "NOT_ENOUGH",
    "USER_NOT_EXIST",
}


def classify_create_error(code):
    """错误码 → 'QUERY_FIRST'（先查单） | 'FINAL_FAIL'（确定性失败）。"""
    if code in QUERY_FIRST_CODES or code == "NETWORK_ERROR":
        return "QUERY_FIRST"
    return "FINAL_FAIL"


def build_transfer_payload(
    *,
    appid,
    out_bill_no,
    openid,
    amount_decimal,
    remark,
    transfer_scene_id,
    scene_report_infos,
    notify_url=None,
    user_recv_perception=None,
    user_name_encrypted=None,
):
    """构造发起转账请求体（金额元→分，对齐 2025.03.21 文档字段）。"""
    amount_cents = int((Decimal(str(amount_decimal)) * 100).to_integral_value())
    payload = {
        "appid": appid,
        "out_bill_no": out_bill_no,
        "transfer_scene_id": transfer_scene_id,
        "openid": openid,
        "transfer_amount": amount_cents,
        "transfer_remark": remark[:32],
        "transfer_scene_report_infos": scene_report_infos,
    }
    if notify_url:
        payload["notify_url"] = notify_url
    if user_recv_perception:
        payload["user_recv_perception"] = user_recv_perception
    if user_name_encrypted:
        payload["user_name"] = user_name_encrypted
    return payload


def normalize_create(resp):
    """归一化发起转账响应 → (state大写, transfer_bill_no)。"""
    return (resp.get("state") or "").upper(), resp.get("transfer_bill_no")


def normalize_query(resp):
    """归一化查单响应 → dict（state大写）。"""
    return {
        "state": (resp.get("state") or "").upper(),
        "transfer_bill_no": resp.get("transfer_bill_no"),
        "fail_reason": resp.get("fail_reason"),
        "success_time": resp.get("success_time"),
    }
