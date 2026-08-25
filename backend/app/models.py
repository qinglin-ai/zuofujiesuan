"""业务数据模型（对应《数据库结构说明.md》，集合映射为关系表）。"""
from datetime import datetime

from .extensions import db


class TimestampMixin:
    create_time = db.Column(db.DateTime, default=datetime.utcnow)


class User(TimestampMixin, db.Model):
    """users 用户表。"""
    __tablename__ = "users"
    __table_args__ = (
        db.UniqueConstraint("openid", name="uk_users_openid"),
        db.UniqueConstraint("phone", name="uk_users_phone"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    openid = db.Column(db.String(64), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    real_name = db.Column(db.String(50), nullable=False)
    avatar = db.Column(db.String(255))
    nickname = db.Column(db.String(50))
    role = db.Column(db.Enum("worker", "admin"), nullable=False, default="worker")
    approval_status = db.Column(
        db.Enum("pending", "approved", "rejected"),
        nullable=False,
        default="pending",
    )
    status = db.Column(db.Enum("active", "blocked"), nullable=False, default="active")
    bank_info = db.Column(db.JSON)  # {bankName, cardNo, cardHolder}
    inviter_openid = db.Column(db.String(64))


class Balance(db.Model):
    """balances 用户佣金账户表。"""
    __tablename__ = "balances"
    __table_args__ = (db.UniqueConstraint("openid", name="uk_balances_openid"),)

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    openid = db.Column(db.String(64), nullable=False)
    available_balance = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Certification(db.Model):
    """certifications 能力认证表。"""
    __tablename__ = "certifications"
    __table_args__ = (
        db.UniqueConstraint(
            "openid", "task_id", "annot_type", name="uk_cert_openid_task_annot"
        ),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    openid = db.Column(db.String(64), nullable=False)
    task_id = db.Column(db.Integer, nullable=False)
    task_name = db.Column(db.String(100))
    annot_type = db.Column(
        db.Enum("shadow", "light_source", "reflection", "exposure", "filter")
    )
    level = db.Column(db.Enum("junior", "middle", "senior"))
    exam_passed = db.Column(db.Boolean, default=False)
    pass_rate = db.Column(db.Numeric(5, 2))
    reviewed_by = db.Column(db.String(64))
    review_time = db.Column(db.DateTime)
    update_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Task(db.Model):
    """tasks 任务表。"""
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(100), nullable=False)
    annot_type = db.Column(
        db.Enum("shadow", "light_source", "reflection", "exposure", "filter")
    )
    quantity = db.Column(db.Integer, nullable=False)
    claimed_count = db.Column(db.Integer, nullable=False, default=0)
    total_people = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)  # 单个作业佣金
    difficulty = db.Column(db.Enum("junior", "middle", "senior"))
    require_level = db.Column(db.Enum("junior", "middle", "senior"))
    deadline = db.Column(db.DateTime)
    status = db.Column(db.Enum("open", "inProgress", "closed"), nullable=False, default="open")
    owner_id = db.Column(db.Integer, nullable=False)
    forbidden_items = db.Column(db.JSON)
    sample_url = db.Column(db.String(255))
    create_time = db.Column(db.DateTime, default=datetime.utcnow)


class Assignment(db.Model):
    """assignments 领单/作业表。一个用户可领取多任务，一人一任务仅一条。"""
    __tablename__ = "assignments"
    __table_args__ = (
        db.UniqueConstraint("openid", "task_id", name="uk_assign_openid_task"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    openid = db.Column(db.String(64), nullable=False)
    task_id = db.Column(db.Integer, nullable=False)
    task_name = db.Column(db.String(100))
    status = db.Column(
        db.Enum("claimed", "submitted", "passed", "rejected"),
        nullable=False,
        default="claimed",
    )
    zh_instruction = db.Column(db.Text)
    en_instruction = db.Column(db.Text)
    submit_time = db.Column(db.DateTime)
    checked_by = db.Column(db.String(64))
    audit_time = db.Column(db.DateTime)
    finish_time = db.Column(db.DateTime)


class QualityCheck(db.Model):
    """quality_checks 外部核验结果表。"""
    __tablename__ = "quality_checks"
    __table_args__ = (
        db.UniqueConstraint("assignment_id", name="uk_qc_assignment"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    assignment_id = db.Column(db.Integer, nullable=False)
    openid = db.Column(db.String(64), nullable=False)
    task_id = db.Column(db.Integer, nullable=False)
    checked_by = db.Column(db.String(64))
    result = db.Column(db.Enum("pass", "reject"), nullable=False)
    external_ref_no = db.Column(db.String(64))
    remark = db.Column(db.String(255))
    check_time = db.Column(db.DateTime, default=datetime.utcnow)


class Commission(db.Model):
    """commissions 佣金流水表。"""
    __tablename__ = "commissions"
    __table_args__ = (
        db.UniqueConstraint("assignment_id", name="uk_comm_assignment"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    openid = db.Column(db.String(64), nullable=False)
    task_id = db.Column(db.Integer, nullable=False)
    assignment_id = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)  # = 来源任务单价
    settle_date = db.Column(db.Date, nullable=False)
    create_time = db.Column(db.DateTime, default=datetime.utcnow)


class Withdrawal(db.Model):
    """withdrawals 提现表（免审核）。"""
    __tablename__ = "withdrawals"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    openid = db.Column(db.String(64), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    bank_account = db.Column(db.JSON)  # {bankName, cardNo, cardHolder}
    status = db.Column(db.Enum("pending", "paid", "rejected"), nullable=False, default="pending")
    pay_ref_no = db.Column(db.String(64))
    paid_source = db.Column(db.Enum("auto", "manual"))
    apply_time = db.Column(db.DateTime, default=datetime.utcnow)
    paid_time = db.Column(db.DateTime)


class Violation(db.Model):
    """violations 违规表。"""
    __tablename__ = "violations"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    openid = db.Column(db.String(64), nullable=False)
    user_name = db.Column(db.String(50))
    type = db.Column(
        db.Enum("alter_original", "edit_jitter", "submit_irrelevant", "other")
    )
    punish_level = db.Column(db.Enum("warning", "suspend", "block"))
    reason = db.Column(db.String(255))
    operator_id = db.Column(db.Integer, nullable=False)
    create_time = db.Column(db.DateTime, default=datetime.utcnow)


class Notice(db.Model):
    """notices 公告表。"""
    __tablename__ = "notices"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    target = db.Column(db.Enum("all", "worker", "admin", "skill"), nullable=False, default="all")
    type = db.Column(
        db.Enum("notice", "flow", "project", "faq"), nullable=False, default="notice"
    )
    create_time = db.Column(db.DateTime, default=datetime.utcnow)