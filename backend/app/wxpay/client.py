"""微信支付 APIv3 客户端：请求签名 + 商家转账接口封装。

- 请求头：WECHATPAY2-SHA256-RSA2048（商户 API 私钥签名）
- 含敏感加密字段(user_name)时带 Wechatpay-Serial=微信支付公钥ID
- 回调验签：微信支付公钥 + Wechatpay-Serial 比对（防公钥轮换攻击）
"""
import json
import time
import uuid

import requests

from . import crypto


class WxpayError(Exception):
    """微信支付接口错误。code 为微信错误码（网络异常为 NETWORK_ERROR）。"""

    def __init__(self, code, message, status_code=0):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class WxpayClient:
    BASE_URL = "https://api.mch.weixin.qq.com"

    def __init__(
        self,
        *,
        mchid,
        serial_no,
        private_key_path,
        api_v3_key,
        platform_public_key_path,
        platform_public_key_id,
        base_url=None,
        timeout=10,
    ):
        self.mchid = mchid
        self.serial_no = serial_no
        self.api_v3_key = api_v3_key.encode("utf-8") if isinstance(api_v3_key, str) else api_v3_key
        self.timeout = timeout
        self.base_url = base_url or self.BASE_URL
        self._private_key = crypto.load_private_key(private_key_path)
        self._platform_public_key = crypto.load_public_key(platform_public_key_path)
        self._platform_public_key_id = platform_public_key_id

    def encrypt_user_name(self, user_name):
        """微信支付公钥加密收款姓名（RSA-OAEP(SHA-1)+base64）。"""
        return crypto.encrypt_user_name(user_name, self._platform_public_key)

    def _auth_headers(self, method, url_path, body_json, sensitive=False):
        timestamp = str(int(time.time()))
        nonce = uuid.uuid4().hex
        message = f"{method}\n{url_path}\n{timestamp}\n{nonce}\n{body_json}\n"
        signature = crypto.sign_rsa_sha256(self._private_key, message.encode("utf-8"))
        auth = (
            "WECHATPAY2-SHA256-RSA2048 "
            f'mchid="{self.mchid}",nonce_str="{nonce}",timestamp="{timestamp}",'
            f'serial_no="{self.serial_no}",signature="{signature}"'
        )
        headers = {
            "Authorization": auth,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "wxpay-flask/1.0",
        }
        if sensitive:
            # 请求含微信支付公钥加密的敏感字段时，须带微信支付公钥ID
            headers["Wechatpay-Serial"] = self._platform_public_key_id
        return headers

    def _request(self, method, url_path, payload=None, sensitive=False):
        body_json = (
            json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            if payload is not None
            else ""
        )
        url = f"{self.base_url}{url_path}"
        headers = self._auth_headers(method, url_path, body_json, sensitive=sensitive)
        try:
            resp = requests.request(
                method, url, headers=headers,
                data=body_json.encode("utf-8") if body_json else None,
                timeout=self.timeout,
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            # 网络异常 = 结果未知，调用方必须先查单、绝不能直接换单
            raise WxpayError("NETWORK_ERROR", f"请求微信支付接口失败: {exc}", 0) from exc

        if resp.status_code >= 300:
            data = _safe_json(resp)
            raise WxpayError(
                (data or {}).get("code") or "UNKNOWN",
                (data or {}).get("message") or resp.text[:200],
                resp.status_code,
            )
        return _safe_json(resp) or {}

    # ---------- 商家转账到零钱 ----------

    def create_transfer_bill(self, payload):
        """发起转账：POST /v3/fund-app/mch-transfer/transfer-bills"""
        return self._request(
            "POST",
            "/v3/fund-app/mch-transfer/transfer-bills",
            payload,
            sensitive=bool(payload.get("user_name")),
        )

    def query_transfer_bill(self, out_bill_no):
        """按商户单号查单：GET /v3/fund-app/mch-transfer/transfer-bills/out-bill-no/{out_bill_no}"""
        return self._request(
            "GET",
            f"/v3/fund-app/mch-transfer/transfer-bills/out-bill-no/{out_bill_no}",
        )

    def cancel_transfer_bill(self, out_bill_no):
        """撤销转账：POST /v3/fund-app/mch-transfer/transfer-bills/out-bill-no/{out_bill_no}/cancel"""
        return self._request(
            "POST",
            f"/v3/fund-app/mch-transfer/transfer-bills/out-bill-no/{out_bill_no}/cancel",
        )

    # ---------- 异步回调 ----------

    def verify_notify(self, headers, raw_body):
        """验证回调签名；Wechatpay-Serial 必须等于配置的微信支付公钥ID。"""
        ts = headers.get("Wechatpay-Timestamp")
        nonce = headers.get("Wechatpay-Nonce")
        signature = headers.get("Wechatpay-Signature")
        serial = headers.get("Wechatpay-Serial")
        if not (ts and nonce and signature):
            return False
        if serial != self._platform_public_key_id:
            return False
        message = f"{ts}\n{nonce}\n{raw_body.decode('utf-8')}\n"
        return crypto.verify_rsa_sha256(
            self._platform_public_key, message.encode("utf-8"), signature
        )

    def decrypt_notify_resource(self, resource):
        return crypto.decrypt_notify_resource(resource, self.api_v3_key)


def _safe_json(resp):
    try:
        return resp.json()
    except Exception:
        return None
