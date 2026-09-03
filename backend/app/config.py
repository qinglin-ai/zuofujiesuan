"""集中配置。优先读取环境变量，未设置时使用 .env（经 load_dotenv 注入）。"""
import json
import os


def _parse_json_env(key, default):
    """读取 JSON 格式环境变量，解析失败回退默认值。"""
    raw = (os.environ.get(key) or "").strip()
    if not raw:
        return default
    try:
        return json.loads(raw)
    except ValueError:
        return default


class Config:
    SECRET_KEY = os.environ.get("JWT_SECRET", "dev-secret")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DB_URI", "mysql+pymysql://root:root@127.0.0.1:3306/zuofu_parttime?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JWT_SECRET = os.environ.get("JWT_SECRET", "dev-jwt-secret")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRE_HOURS = int(os.environ.get("JWT_EXPIRE_HOURS", "72"))

    # 微信配置（未注册时留空）
    WX_APPID = os.environ.get("WX_APPID", "")
    WX_SECRET = os.environ.get("WX_SECRET", "")

    # 微信支付 商家转账到零钱（自动打款）
    WX_MCHID = os.environ.get("WX_MCHID", "")  # 商户号
    WXPAY_ENABLED = os.environ.get("WXPAY_ENABLED", "0").strip().lower() in ("1", "true", "yes")
    WXPAY_MOCK = os.environ.get("WXPAY_MOCK", "0").strip().lower() in ("1", "true", "yes")
    WXPAY_API_V3_KEY = os.environ.get("WXPAY_API_V3_KEY", "")  # 32位 APIv3 密钥
    WXPAY_MCH_SERIAL_NO = os.environ.get("WXPAY_MCH_SERIAL_NO", "")  # 商户API证书序列号
    WXPAY_MCH_PRIVATE_KEY_PATH = os.environ.get(
        "WXPAY_MCH_PRIVATE_KEY_PATH", "certs/apiclient_key.pem"
    )
    WXPAY_PLATFORM_PUBLIC_KEY_PATH = os.environ.get(
        "WXPAY_PLATFORM_PUBLIC_KEY_PATH", "certs/pub_key.pem"
    )
    WXPAY_PLATFORM_PUBLIC_KEY_ID = os.environ.get("WXPAY_PLATFORM_PUBLIC_KEY_ID", "")  # 微信支付公钥ID
    WXPAY_NOTIFY_URL = os.environ.get("WXPAY_NOTIFY_URL", "")  # 公网 HTTPS 回调地址
    WXPAY_TRANSFER_SCENE_ID = os.environ.get("WXPAY_TRANSFER_SCENE_ID", "1000")
    WXPAY_SCENE_REPORT_INFOS = _parse_json_env(
        "WXPAY_SCENE_REPORT_INFOS",
        [{"info_type": "提现说明", "info_content": "兼职佣金提现"}],
    )
    WXPAY_RETRY_MAX = int(os.environ.get("WXPAY_RETRY_MAX", "1"))
    WXPAY_HTTP_TIMEOUT = int(os.environ.get("WXPAY_HTTP_TIMEOUT", "10"))