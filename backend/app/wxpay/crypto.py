"""微信支付 APIv3 加解密与签名（纯函数，不依赖 Flask/DB）。

依赖 cryptography 43.x：
- RSA-SHA256 请求签名 / 回调验签（PKCS1v15）
- RSA-OAEP(SHA-1) 收款用户姓名加密（微信支付强制 SHA-1）
- AES-256-GCM 回调 resource 解密
"""
import base64
import json

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def load_private_key(path):
    """加载商户 API 私钥（apiclient_key.pem，PKCS#8 PEM）。"""
    with open(path, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def load_public_key(path):
    """加载微信支付公钥（wxp_pub.pem，PKCS#1/PKCS#8 PEM 均可）。"""
    with open(path, "rb") as f:
        return serialization.load_pem_public_key(f.read())


def sign_rsa_sha256(private_key, message: bytes) -> str:
    """RSA-SHA256 签名，返回 base64 字符串。"""
    signature = private_key.sign(message, padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(signature).decode()


def verify_rsa_sha256(public_key, message: bytes, signature_b64: str) -> bool:
    """用公钥验签，验签失败返回 False（不抛异常）。"""
    try:
        public_key.verify(
            base64.b64decode(signature_b64), message, padding.PKCS1v15(), hashes.SHA256()
        )
        return True
    except Exception:
        return False


def encrypt_user_name(user_name: str, public_key) -> str:
    """收款用户姓名加密：RSA-OAEP(SHA-1) + base64（微信支付强制 SHA-1）。"""
    encrypted = public_key.encrypt(
        user_name.encode("utf-8"),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA1()),
            algorithm=hashes.SHA1(),
            label=None,
        ),
    )
    return base64.b64encode(encrypted).decode()


def decrypt_notify_resource(resource: dict, api_v3_key: bytes) -> dict:
    """AES-256-GCM 解密回调 resource（ciphertext/nonce/associated_data）→ JSON dict。"""
    nonce = resource["nonce"].encode("utf-8")
    associated_data = resource.get("associated_data", "").encode("utf-8")
    ciphertext = base64.b64decode(resource["ciphertext"])
    plaintext = AESGCM(api_v3_key).decrypt(nonce, ciphertext, associated_data)
    return json.loads(plaintext.decode("utf-8"))
