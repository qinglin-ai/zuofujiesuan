"""提现合规整改冒烟验证（sqlite 内存库 + test_client，不依赖 Docker/MySQL）。

覆盖：
1. 提现规则返回（/api/wallet/me 的 withdraw_rule 字段）
2. 绑卡必须显式授权（agree=true），未授权 400
3. 每日提现次数上限（默认 1 次，第二次 400）
4. 跨天不影响（昨日申请不计入今日次数）

运行：python _verify_withdraw_rules.py
"""
import os
import sys
from datetime import datetime, timedelta

os.environ.setdefault("JWT_SECRET", "verify-secret")
os.environ.setdefault(
    "DB_URI", "sqlite+pysqlite:///:memory:"
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.pool import StaticPool  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Balance, User, Withdrawal  # noqa: E402
from app.auth import create_token  # noqa: E402

OPENID = "openid_verify_user"

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {name}{(' -> ' + detail) if detail else ''}")


def build_app():
    app = create_app()
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite+pysqlite:///:memory:"
    app.config["WXPAY_ENABLED"] = False  # 关闭自动打款，只验证规则校验
    app.config["WITHDRAW_DAILY_MAX"] = 1
    app.config["TESTING"] = True
    app.config["PROPAGATE_EXCEPTIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "connect_args": {"check_same_thread": False},
        "poolclass": StaticPool,
    }
    return app


def main():
    app = build_app()
    with app.app_context():
        db.create_all()
        db.session.add(
            User(
                openid=OPENID,
                phone="13800000000",
                real_name="验证用户",
                role="worker",
                status="active",
                approval_status="approved",
            )
        )
        db.session.add(Balance(openid=OPENID, available_balance=100))
        db.session.commit()
        token = create_token(OPENID, "worker")

    headers = {"Authorization": f"Bearer {token}"}
    client = app.test_client()

    # 1) 提现规则返回
    res = client.get("/api/wallet/me", headers=headers)
    rule = (res.get_json() or {}).get("data", {}).get("withdraw_rule") or {}
    check("1. /api/wallet/me 返回提现规则", rule.get("daily_limit") == 1, str(rule))
    check("1.1 今日初始剩余次数=上限", rule.get("today_remaining") == 1, str(rule))

    # 2) 未授权绑卡被拒绝
    res = client.post(
        "/api/wallet/bank",
        headers=headers,
        json={"bankName": "招商银行", "cardNo": "6225880133334444", "cardHolder": "验证用户"},
    )
    check("2. 未授权绑卡 400", res.status_code == 400, res.get_json().get("message"))

    # 2.1) 授权后绑卡成功
    res = client.post(
        "/api/wallet/bank",
        headers=headers,
        json={
            "bankName": "招商银行",
            "cardNo": "6225880133334444",
            "cardHolder": "验证用户",
            "agree": True,
        },
    )
    check("2.1 授权后绑卡成功", res.status_code == 200, res.get_json().get("message"))

    # 3) 首次提现成功
    res = client.post("/api/wallet/withdrawals", headers=headers, json={"amount": "10"})
    check("3. 首次提现申请成功", res.status_code == 200, res.get_json().get("message"))

    # 3.1) 同日第二次提现被拒绝
    res = client.post("/api/wallet/withdrawals", headers=headers, json={"amount": "10"})
    msg = (res.get_json() or {}).get("message")
    check("3.1 同日第二次提现 400", res.status_code == 400, msg)
    check("3.2 拒绝原因含次数规则", "每日最多 1 次" in (msg or ""), msg)

    # 3.3) 规则中今日已用次数为 1、剩余 0
    res = client.get("/api/wallet/me", headers=headers)
    rule = (res.get_json() or {}).get("data", {}).get("withdraw_rule") or {}
    check("3.3 今日已用=1 剩余=0", rule.get("today_used") == 1 and rule.get("today_remaining") == 0, str(rule))

    # 4) 昨日申请不计入今日次数
    with app.app_context():
        w = db.session.execute(db.select(Withdrawal)).scalars().first()
        w.apply_time = datetime.utcnow() - timedelta(days=1)
        db.session.commit()
        balance = db.session.execute(db.select(Balance)).scalars().first()
        balance.available_balance = 100
        db.session.commit()
    res = client.get("/api/wallet/me", headers=headers)
    rule = (res.get_json() or {}).get("data", {}).get("withdraw_rule") or {}
    check("4. 跨天次数重置（剩余=1）", rule.get("today_remaining") == 1, str(rule))

    failed = [r for r in results if not r[1]]
    print("\n" + "=" * 46)
    print(f"共 {len(results)} 项，通过 {len(results) - len(failed)} 项，失败 {len(failed)} 项")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())