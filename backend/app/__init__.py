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

    # 注册 CLI 命令
    from .cli import register_commands

    register_commands(app)

    # 注册蓝图
    from .api.auth import bp as auth_bp
    from .api.health import bp as health_bp
    from .api.users import bp as users_bp
    from .api.certifications import bp as certificates_bp
    from .api import tasks as tasks_module
    from .api.quality import bp as quality_bp
    from .api.violations import bp as violations_bp
    from .api.notices import bp as notices_bp
    from .api.wallet import bp as wallet_bp
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(health_bp, url_prefix="/api/health")
    app.register_blueprint(users_bp, url_prefix="/api/users")
    app.register_blueprint(certificates_bp, url_prefix="/api/certifications")
    app.register_blueprint(tasks_module.bp, url_prefix="/api/tasks")
    app.register_blueprint(quality_bp, url_prefix="/api/quality-checks")
    app.register_blueprint(violations_bp, url_prefix="/api/violations")
    app.register_blueprint(notices_bp, url_prefix="/api/notices")
    app.register_blueprint(wallet_bp, url_prefix="/api/wallet")

    # 管理后台 H5 入口（阶段五）
    @app.get("/admin")
    def admin_index():
        return app.send_static_file("admin/index.html")

    return app