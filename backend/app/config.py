"""集中配置。优先读取环境变量，未设置时使用 .env（经 load_dotenv 注入）。"""
import os


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