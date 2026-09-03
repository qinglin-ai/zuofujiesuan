"""Flask CLI 命令（管理后台初始化辅助）。"""
import click
from sqlalchemy import or_
from werkzeug.security import generate_password_hash

from .extensions import db
from .models import User


def register_commands(app):
    @app.cli.command("seed-admin")
    @click.option(
        "--account",
        prompt="管理员账号(手机号/真实姓名)",
        default="",
        help="将该用户设为 admin",
    )
    @click.option(
        "--password",
        prompt="密码",
        hide_input=True,
        confirmation_prompt=True,
        help="登录密码",
    )
    def seed_admin(account, password):
        """将已建档用户设为 admin 并设置登录密码（T5-1 引导用）。"""
        account = (account or "").strip()
        user = db.session.execute(
            db.select(User).where(
                or_(User.phone == account, User.real_name == account)
            )
        ).scalar_one_or_none()
        if not user:
            click.echo("未找到该用户，请先用微信小程序登录建档后再执行 seed-admin")
            return
        user.role = "admin"
        user.password_hash = generate_password_hash(password)
        db.session.commit()
        click.echo(f"已将用户[{account}]设为 admin 并设置登录密码")

    @app.cli.command("wxpay-selfcheck")
    def wxpay_selfcheck():
        """微信支付协议层自检（签名/加密/解密/防重决策表，零凭据零依赖）。"""
        from .wxpay import selfcheck as run_selfcheck

        results = run_selfcheck()
        ok = True
        for name, passed in results:
            ok = ok and passed
            click.echo(f"[{'OK' if passed else 'FAIL'}] {name}")
        click.echo("微信支付自检通过" if ok else "微信支付自检存在失败项")