"""本地模拟微信支付客户端（WXPAY_MOCK=1，无需真实凭据/网络）。

用于本地开发打通「申请提现→自动打款→状态回写」全链路：
- create 返回 ACCEPTED（非终态，等待回调/查单）
- query 返回 SUCCESS（对账/补发时按已到账处理）
- 回调验签直接放行
"""
import base64
import json
import time


class MockClient:
    mode = "mock"

    def __init__(self, **kwargs):
        pass

    def encrypt_user_name(self, user_name):
        return None  # mock 不加密，payload 中省略 user_name

    def create_transfer_bill(self, payload):
        return {
            "out_bill_no": payload["out_bill_no"],
            "transfer_bill_no": f"MOCK{int(time.time() * 1000)}",
            "create_time": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "state": "ACCEPTED",
        }

    def query_transfer_bill(self, out_bill_no):
        return {
            "out_bill_no": out_bill_no,
            "transfer_bill_no": f"MOCK{int(time.time() * 1000)}",
            "state": "SUCCESS",
            "success_time": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        }

    def cancel_transfer_bill(self, out_bill_no):
        return {"out_bill_no": out_bill_no, "state": "CANCELLED"}

    def verify_notify(self, headers, raw_body):
        return True  # mock 跳过验签

    def decrypt_notify_resource(self, resource):
        return json.loads(base64.b64decode(resource["ciphertext"]).decode("utf-8"))
