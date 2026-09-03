"""临时验证脚本：wxpay 自检 + 防重逻辑测试。

- SQLite :memory: + StaticPool（单连接共享），避免跨会话丢数据
- 单一 app/上下文，场景间 drop_all+create_all 隔离
- 脚本化 mock 客户端模拟 创建失败/查单FAIL/确定性失败 等防重场景
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 强制 SQLite 内存库 + 启用 mock 自动打款，绝不触碰 MySQL/真实凭据
os.environ["DB_URI"] = "sqlite:///:memory:"
os.environ["WXPAY_ENABLED"] = "1"
os.environ["WXPAY_MOCK"] = "1"

from sqlalchemy.pool import StaticPool
from flask import current_app

from app import create_app
from app.wxpay import selfcheck
from app.extensions import db
from app.models import Balance, User, Withdrawal
from app.api.wallet import (
    auto_transfer_withdrawal,
    handle_transfer_event,
    _gen_out_bill_no,
)
from app import wxpay
from app.wxpay import WxpayError
from app.wxpay.mock import MockClient

app = create_app()
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "poolclass": StaticPool,
    "connect_args": {"check_same_thread": False},
}
ctx = app.app_context()
ctx.push()

PASS = []
FAIL = []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(f"[{'OK' if cond else 'FAIL'}] {name}")


def reset_db():
    db.drop_all()
    db.create_all()
    u = User(openid="openid_test_001", phone="13800000000", real_name="张三", role="worker")
    db.session.add(u)
    db.session.add(Balance(openid="openid_test_001", available_balance=1000))
    db.session.commit()
    return u


def set_client(obj):
    # 生产代码 get_client 的缓存键是 id(current_app)（LocalProxy），测试须一致
    wxpay._client_cache[id(current_app)] = obj


def add_withdrawal(openid, amount):
    w = Withdrawal(openid=openid, amount=amount, bank_account={"cardNo": "1"}, status="pending")
    db.session.add(w)
    db.session.commit()
    return w


def test_selfcheck():
    for name, passed in selfcheck():
        check(f"selfcheck: {name}", passed)


def test_auto_transfer_success():
    """场景A：mock 创建即 ACCEPTED（非终态）→ 保持 pending，回调 SUCCESS → paid（幂等）。"""
    set_client(MockClient())
    u = reset_db()
    w = add_withdrawal(u.openid, 50)
    st = auto_transfer_withdrawal(w)
    db.session.refresh(w)
    check("A1 非终态保持 pending", st == "pending" and w.status == "pending")
    check("A2 已记录 out_bill_no", bool(w.out_bill_no and w.out_bill_no.startswith("WD")))
    check("A3 镜像 ACCEPTED", w.transfer_status == "ACCEPTED")
    check("A4 未到终态无 paid_time", w.paid_time is None)

    ev = {"out_bill_no": w.out_bill_no, "state": "SUCCESS", "transfer_bill_no": "WX_T1"}
    check("A5 回调处理成功", handle_transfer_event(w.out_bill_no, ev) is True)
    db.session.refresh(w)
    check("A6 回调后已到账", w.status == "paid" and w.paid_source == "auto" and w.paid_time is not None)
    check("A7 幂等重复回调", handle_transfer_event(w.out_bill_no, ev) is True)
    db.session.refresh(w)
    check("A8 幂等不重复到账", w.status == "paid")


def test_query_first_retry():
    """场景B：创建遇 ALREADY_EXISTS → 查单明确 FAIL → 换新单号重试一次 → 成功。"""
    class ScriptedClient(MockClient):
        calls = {"create": 0, "query": 0}

        def create_transfer_bill(self, payload):
            self.calls["create"] += 1
            if self.calls["create"] == 1:
                raise WxpayError("ALREADY_EXISTS", "订单已存在", 400)
            return {"out_bill_no": payload["out_bill_no"], "state": "SUCCESS",
                    "transfer_bill_no": f"WX_B{self.calls['create']}"}

        def query_transfer_bill(self, out_bill_no):
            self.calls["query"] += 1
            return {"out_bill_no": out_bill_no, "state": "FAIL", "fail_reason": "金额超限(测试)"}

    set_client(ScriptedClient())
    u = reset_db()
    w = add_withdrawal(u.openid, 5000)
    st = auto_transfer_withdrawal(w)
    db.session.refresh(w)
    check("B1 换单重试后成功", st == "paid" and w.status == "paid")
    check("B2 查询过原单(防重)", ScriptedClient.calls["query"] == 1)
    check("B3 使用最新单号", w.out_bill_no == _gen_out_bill_no(w.id, 1))
    check("B4 重试计数=1", w.retry_count == 1)
    check("B5 换单号递增唯一", _gen_out_bill_no(w.id, 0) != _gen_out_bill_no(w.id, 1))


def test_deterministic_fail():
    """场景C：确定性错误 PARAM_ERROR → 直接转人工，不查单不重试。"""
    class FailClient(MockClient):
        def create_transfer_bill(self, payload):
            raise WxpayError("PARAM_ERROR", "参数错误", 400)

        def query_transfer_bill(self, out_bill_no):
            raise AssertionError("确定性失败不应查单")

    set_client(FailClient())
    u = reset_db()
    w = add_withdrawal(u.openid, 30)
    st = auto_transfer_withdrawal(w)
    db.session.refresh(w)
    check("C1 确定性失败置 rejected", st == "rejected" and w.status == "rejected")
    check("C2 失败原因含 PARAM_ERROR", "PARAM_ERROR" in (w.fail_reason or ""))
    check("C3 不重试(retry_count=0)", w.retry_count == 0)


def test_retry_exhausted_rejected():
    """场景D：查单明确 FAIL 且已达重试上限 → 置 rejected 转人工。"""
    class AlwaysFail(MockClient):
        def create_transfer_bill(self, payload):
            raise WxpayError("SYSTEM_ERROR", "系统异常", 500)

        def query_transfer_bill(self, out_bill_no):
            return {"out_bill_no": out_bill_no, "state": "FAIL", "fail_reason": "余额不足(测试)"}

    set_client(AlwaysFail())
    u = reset_db()
    w = add_withdrawal(u.openid, 60)
    st = auto_transfer_withdrawal(w)
    db.session.refresh(w)
    check("D1 重试上限后 rejected", st == "rejected" and w.status == "rejected")
    check("D2 重试计数=上限", w.retry_count == int(app.config.get("WXPAY_RETRY_MAX", 1)))
    check("D3 镜像 FAIL", w.transfer_status == "FAIL")


def test_stale_notify():
    """场景E：陈旧回调（旧单号已被换单）→ 忽略。"""
    u = reset_db()
    w = add_withdrawal(u.openid, 10)
    old_no = _gen_out_bill_no(w.id, 0)
    w.out_bill_no = old_no
    w.transfer_status = "FAIL"
    w.retry_count = 1
    db.session.commit()
    w2 = db.session.get(Withdrawal, w.id)
    w2.out_bill_no = _gen_out_bill_no(w.id, 1)  # 已换新单号
    db.session.commit()
    stale = {"out_bill_no": old_no, "state": "SUCCESS"}
    check("E1 陈旧回调被忽略", handle_transfer_event(old_no, stale) is False)
    db.session.refresh(w)
    check("E2 状态未被陈旧回调改写", w.status == "pending" and w.out_bill_no == _gen_out_bill_no(w.id, 1))


def test_notify_fail_then_retry():
    """场景F：回调 FAIL → 未达上限自动换单重试 → 成功。"""
    class FailThenOk(MockClient):
        def __init__(self):
            self.called = False

        def create_transfer_bill(self, payload):
            return {"out_bill_no": payload["out_bill_no"], "state": "ACCEPTED",
                    "transfer_bill_no": f"WX_F{payload['out_bill_no']}"}

        def query_transfer_bill(self, out_bill_no):
            return {"out_bill_no": out_bill_no, "state": "SUCCESS",
                    "success_time": "2026-09-03T12:00:00+08:00"}

    set_client(FailThenOk())
    u = reset_db()
    w = add_withdrawal(u.openid, 20)
    # 先模拟同步创建 ACCEPTED
    auto_transfer_withdrawal(w)
    db.session.refresh(w)
    old_no = w.out_bill_no
    # 微信回调 FAIL
    ev = {"out_bill_no": old_no, "state": "FAIL", "fail_reason": "收款方未实名(测试)", "transfer_bill_no": "WX_F_FAIL"}
    check("F1 回调FAIL被处理", handle_transfer_event(old_no, ev) is True)
    db.session.refresh(w)
    check("F2 未达上限自动换单重试", w.out_bill_no != old_no and w.retry_count == 1)
    check("F3 换单后状态 pending", w.status == "pending")
    check("F4 旧单号已镜像FAIL", w.transfer_status in ("FAIL", "ACCEPTED"))


def main():
    test_selfcheck()
    test_auto_transfer_success()
    test_query_first_retry()
    test_deterministic_fail()
    test_retry_exhausted_rejected()
    test_stale_notify()
    test_notify_fail_then_retry()
    print("\n===== 结果 =====")
    print(f"通过 {len(PASS)} 项, 失败 {len(FAIL)} 项")
    if FAIL:
        print("失败项:", FAIL)
        sys.exit(1)
    print("全部通过")
    ctx.pop()


if __name__ == "__main__":
    main()
