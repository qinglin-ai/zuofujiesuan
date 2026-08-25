"""日志基础配置：控制台 + 按天轮转文件（logs/app.log）。"""
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


def setup_logging(app):
    log_dir = Path(app.root_path).parent / "logs"
    log_dir.mkdir(exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    )

    file_handler = TimedRotatingFileHandler(
        log_dir / "app.log", when="midnight", backupCount=14, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    app.logger.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    return app.logger