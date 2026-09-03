"""微信支付「商家转账到零钱」集成（纯协议层，不依赖 models/db）。

对外入口：
- is_enabled(app)         是否启用自动打款
- get_client(app)         懒加载客户端（WXPAY_MOCK=1 返回本地模拟）
- selfcheck()             零凭据自检（签名/加密/解密/决策表）
"""
import base64
import os

from flask import current_app

from .client import WxpayClient, WxpayError
from . import transfer as transfer_api

_client_cache = {}


def is_enabled(app=None):
    """启用自动打款：WXPAY_ENABLED=1 且关键凭据齐备（mock 模式仅需开关）。"""
    app = app or current_app
    if not app.config.get("WXPAY_ENABLED"):
        return False
    if app.config.get("WXPAY_MOCK"):
        return True
    required = (
        "WX_MCHID",
        "WXPAY_API_V3_KEY",
        "WXPAY_MCH_SERIAL_NO",
        "WXPAY_MCH_PRIVATE_KEY_PATH",
        "WXPAY_PLATFORM_PUBLIC_KEY_PATH",
        "WXPAY_PLATFORM_PUBLIC_KEY_ID",
    )
    return all(app.config.get(k) for k in required)


def get_client(app=None):
    """构造/取缓存客户端；未启用返回 None。"""
    app = app or current_app
    if not is_enabled(app):
        return None
    key = id(app)
    if key not in _client_cache:
        if app.config.get("WXPAY_MOCK"):
            from .mock import MockClient

            _client_cache[key] = MockClient()
        else:
            _client_cache[key] = WxpayClient(
                mchid=app.config["WX_MCHID"],
                serial_no=app.config["WXPAY_MCH_SERIAL_NO"],
                private_key_path=app.config["WXPAY_MCH_PRIVATE_KEY_PATH"],
                api_v3_key=app.config["WXPAY_API_V3_KEY"],
                platform_public_key_path=app.config["WXPAY_PLATFORM_PUBLIC_KEY_PATH"],
                platform_public_key_id=app.config["WXPAY_PLATFORM_PUBLIC_KEY_ID"],
                timeout=app.config.get("WXPAY_HTTP_TIMEOUT", 10),
            )
    return _client_cache[key]


def selfcheck():
    """零凭据自检：请求签名回环 / OAEP-SHA1 / AES-GCM / 防重决策表。

    返回 [(名称, 是否通过), ...]，供 `flask wxpay-selfcheck` 打印。
    """
    import json as _json

    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    from . import crypto

    results = []
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = key.public_key()

    # 1. 请求签名/验签回环（微信 message 格式）
    msg = (
        "POST\n/v3/fund-app/mch-transfer/transfer-bills\n"
        "1700000000\ntestnonce\n{}\n"
    ).encode()
    sig = crypto.sign_rsa_sha256(key, msg)
    results.append(("请求签名回环", crypto.verify_rsa_sha256(pub, msg, sig)))

    # 2. 姓名 RSA-OAEP(SHA-1) 加密后可用私钥解密还原
    enc = crypto.encrypt_user_name("张三", pub)
    dec = key.decrypt(
        base64.b64decode(enc),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA1()),
            algorithm=hashes.SHA1(),
            label=None,
        ),
    ).decode("utf-8")
    results.append(("姓名OAEP(SHA-1)加解密", dec == "张三"))

    # 3. AES-256-GCM 回调 resource 解密回环
    aes_key = os.urandom(32)
    nonce = "123456789012"
    aad = "transaction"
    plain = _json.dumps({"state": "SUCCESS"}).encode()
    ct = AESGCM(aes_key).encrypt(nonce.encode(), plain, aad.encode())
    resource = {
        "nonce": nonce,
        "associated_data": aad,
        "ciphertext": base64.b64encode(ct).decode(),
    }
    decrypted = crypto.decrypt_notify_resource(resource, aes_key)
    results.append(("AES-GCM回调解密", decrypted == {"state": "SUCCESS"}))

    # 4. 防重决策表
    qf = {
        "ALREADY_EXISTS",
        "SYSTEM_ERROR",
        "FREQUENCY_LIMIT",
        "FREQUENCY_LIMIT_EXCEED",
        "RATELIMIT_EXCEEDED",
        "NETWORK_ERROR",
    }
    ff = {"PARAM_ERROR", "INVALID_REQUEST", "NO_AUTH", "SIGN_ERROR", "NOT_ENOUGH"}
    results.append(
        ("决策表-QUERY_FIRST", all(transfer_api.classify_create_error(c) == "QUERY_FIRST" for c in qf))
    )
    results.append(
        ("决策表-FINAL_FAIL", all(transfer_api.classify_create_error(c) == "FINAL_FAIL" for c in ff))
    )
    return results
