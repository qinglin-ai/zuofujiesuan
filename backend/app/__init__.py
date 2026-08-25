"""Flask 应用工厂。"""
import os

from dotenv import load_dotenv
from flask import Flask

from .extensions import db
from .config import Config
from .logging_conf import setup_logging

load_dotenv()


def create_app(config_object=None):
    app = Flask(__name__)
    app.config.from_object(config_object or Config)

    db.init_app(app)
    setup_logging(app)

    # 注册蓝图
    from .api.auth import bp as auth_bp
    from .api.health import bp as health_bp
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(health_bp, url_prefix="/api/health")

    return app