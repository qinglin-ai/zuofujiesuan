"""WSGI 入口：生产以 gunicorn app.wsgi:app 运行。"""
from app import create_app

app = create_app()


if __name__ == "__main__":
    import os
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=debug)