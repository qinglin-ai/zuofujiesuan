"""Flask 扩展实例（延迟绑定到 app）。"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
jwt = {}  # JWT 辅助函数放 auth/utils，此处保留占位以统一扩展入口