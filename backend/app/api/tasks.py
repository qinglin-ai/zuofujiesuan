"""任务发布/浏览/领取/提交接口（阶段三 T3-3 / T3-4(需登录) / T3-5 / T3-6）。

核心：T3-5 领取用「条件原子自增 claimed_count + 唯一索引(openid, task_id)」双保险防并发超领。
"""
from datetime import datetime

from flask import Blueprint, g, request
from sqlalchemy.exc import IntegrityError

from ..auth import login_required, require_role
from ..extensions import db
from ..models import Assignment, Certification, Task

bp = Blueprint("tasks", __name__)

VALID_ANNOT = {"shadow", "light_source", "reflection", "exposure", "filter"}
VALID_LEVEL = {"junior", "middle", "senior"}
_LEVEL_RANK = {"junior": 1, "middle": 2, "senior": 3}


def _public_task(task):
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "annot_type": task.annot_type,
        "quantity": task.quantity,
        "claimed_count": task.claimed_count,
        "total_people": task.total_people,
        "unit_price": str(task.unit_price) if task.unit_price is not None else None,
        "difficulty": task.difficulty,
        "require_level": task.require_level,
        "deadline": task.deadline.isoformat() if task.deadline else None,
        "status": task.status,
        "owner_id": task.owner_id,
        "forbidden_items": task.forbidden_items,
        "sample_url": task.sample_url,
        "create_time": task.create_time.isoformat() if task.create_time else None,
    }


def _public_assignment(assign, task=None):
    task = task or db.session.get(Task, assign.task_id)
    return {
        "id": assign.id,
        "task_id": assign.task_id,
        "task_name": assign.task_name or (task.title if task else None),
        "status": assign.status,
        "annot_type": task.annot_type if task else None,
        "unit_price": str(task.unit_price) if task and task.unit_price is not None else None,
        "submit_time": assign.submit_time.isoformat() if assign.submit_time else None,
        "checked_by": assign.checked_by,
        "audit_time": assign.audit_time.isoformat() if assign.audit_time else None,
        "finish_time": assign.finish_time.isoformat() if assign.finish_time else None,
    }


# ---------- T3-3 任务创建（管理端） ----------

@bp.post("")
@require_role("admin")
def create_task():
    """管理员创建任务，初始 status=open、claimed_count=0。"""
    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "").strip()
    if not title:
        return {"code": 400, "message": "任务名必填"}, 400
    description = (body.get("description") or "").strip() or None

    annot_type = (body.get("annot_type") or "").strip()
    if annot_type and annot_type not in VALID_ANNOT:
        return {"code": 400, "message": "annot_type 无效"}, 400
    difficulty = (body.get("difficulty") or "").strip()
    if difficulty and difficulty not in VALID_LEVEL:
        return {"code": 400, "message": "difficulty 无效"}, 400
    require_level = (body.get("require_level") or "").strip()
    if require_level and require_level not in VALID_LEVEL:
        return {"code": 400, "message": "require_level 无效"}, 400

    for field in ("quantity", "total_people"):
        val = body.get(field)
        if val is None:
            return {"code": 400, "message": f"{field} 必填"}, 400
        try:
            val = int(val)
        except (TypeError, ValueError):
            return {"code": 400, "message": f"{field} 无效"}, 400
        if val <= 0:
            return {"code": 400, "message": f"{field} 需为正整数"}, 400
        body[field] = val

    try:
        unit_price = float(body["unit_price"])
    except (KeyError, TypeError, ValueError):
        return {"code": 400, "message": "unit_price 必填且为数字"}, 400
    if unit_price <= 0:
        return {"code": 400, "message": "unit_price 需为正数"}, 400

    deadline = body.get("deadline")
    if deadline:
        try:
            deadline = datetime.fromisoformat(str(deadline).replace("Z", "+00:00").replace(" ", "T"))
        except ValueError:
            return {"code": 400, "message": "deadline 格式无效"}, 400

    task = Task(
        title=title,
        description=description,
        annot_type=annot_type or None,
        quantity=body["quantity"],
        total_people=body["total_people"],
        unit_price=unit_price,
        difficulty=difficulty or None,
        require_level=require_level or None,
        deadline=deadline,
        status="open",
        claimed_count=0,
        owner_id=g.user.id,
        forbidden_items=body.get("forbidden_items") if isinstance(body.get("forbidden_items"), list) else None,
        sample_url=(body.get("sample_url") or "").strip() or None,
    )
    db.session.add(task)
    db.session.commit()
    return {"code": 0, "data": _public_task(task)}


# ---------- T3-4 任务列表 / 详情 / 我的作业（需登录浏览） ----------

_STATUS_TEXT = {
    "claimed": "已领取",
    "submitted": "已提交",
    "passed": "已通过",
    "rejected": "未通过",
}


@bp.get("/mine")
@login_required
def my_assignments():
    """当前用户已领取的作业列表（T3-8 我的作业页，含可提交的 assignmentId）。"""
    assigns = db.session.execute(
        db.select(Assignment)
        .where(Assignment.openid == g.openid)
        .order_by(Assignment.id.desc())
    ).scalars()
    data = []
    for a in assigns:
        item = _public_assignment(a)
        item["status_text"] = _STATUS_TEXT.get(a.status, a.status)
        data.append(item)
    return {"code": 0, "data": data}


@bp.get("")
@login_required
def list_tasks():
    """任务列表，可加 status 过滤；返回当前用户对该任务的领取状态。"""
    status = (request.args.get("status") or "").strip()
    q = db.select(Task).order_by(Task.id.desc())
    if status:
        q = q.where(Task.status == status)
    tasks = db.session.execute(q).scalars().all()
    my_assigns = {
        a.task_id: a.status
        for a in db.session.execute(
            db.select(Assignment).where(Assignment.openid == g.openid)
        ).scalars()
    }
    data = []
    for t in tasks:
        item = _public_task(t)
        item["my_status"] = my_assigns.get(t.id)
        data.append(item)
    return {"code": 0, "data": data}


@bp.get("/<int:task_id>")
@login_required
def task_detail(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return {"code": 404, "message": "任务不存在"}, 404
    data = _public_task(task)
    mine = db.session.execute(
        db.select(Assignment).where(
            Assignment.openid == g.openid, Assignment.task_id == task_id
        )
    ).scalar_one_or_none()
    data["my_status"] = mine.status if mine else None
    # 本人认证（用于前端展示是否达到领取资格）
    cert = db.session.execute(
        db.select(Certification).where(
            Certification.openid == g.openid,
            Certification.task_id == task_id,
            Certification.annot_type == task.annot_type,
        )
    ).scalar_one_or_none()
    data["my_cert"] = {
        "exam_passed": cert.exam_passed if cert else False,
        "level": cert.level if cert else None,
    } if cert else None
    return {"code": 0, "data": data}


# ---------- T3-5 任务领取（并发超领控制） ----------

def _user_qualified(task):
    """校验用户是否具备领取资格（审批通过 + 认证达标）。"""
    user = g.user
    if user.approval_status != "approved" or user.status != "active":
        return False, "账号未审批通过或已封禁"
    contract = _LEVEL_RANK.get(task.require_level, 1) if task.require_level else 1
    cert = db.session.execute(
        db.select(Certification).where(
            Certification.openid == g.openid,
            Certification.task_id == task.id,
            Certification.annot_type == task.annot_type,
        )
    ).scalar_one_or_none()
    if not cert or not cert.exam_passed or not cert.level:
        return False, "未通过本任务类型准入考试"
    if _LEVEL_RANK.get(cert.level, 0) < contract:
        return False, f"能力等级不足，需 {task.require_level} 以上"
    return True, ""


@bp.post("/<int:task_id>/claim")
@login_required
def claim_task(task_id):
    """领取任务：条件原子自增名额 + 唯一索引防重复，整体事务。"""
    task = db.session.get(Task, task_id)
    if not task:
        return {"code": 404, "message": "任务不存在"}, 404
    if task.status != "open":
        return {"code": 400, "message": "任务未开启或已关闭"}, 400

    ok, reason = _user_qualified(task)
    if not ok:
        return {"code": 403, "message": reason}, 403

    # 并发超领控制：仅未满员且 open 状态才 +1，rowcount==1 表示成功占用名额
    res = db.session.execute(
        db.update(Task)
        .where(
            Task.id == task_id,
            Task.status == "open",
            Task.claimed_count < Task.total_people,
        )
        .values(claimed_count=Task.claimed_count + 1)
    )
    if res.rowcount != 1:
        db.session.rollback()
        return {"code": 409, "message": "任务已满员"}, 409

    # 创建 assignment（唯一索引 uk_assign_openid_task 兜底防重复领取）
    assignment = Assignment(
        openid=g.openid,
        task_id=task_id,
        task_name=task.title,
        status="claimed",
    )
    db.session.add(assignment)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return {"code": 409, "message": "您已领取过该任务"}, 409

    # 满员开工：claimed_count == total_people 时置为 inProgress
    task = db.session.get(Task, task_id)
    if task.claimed_count >= task.total_people:
        task.status = "inProgress"
        db.session.commit()

    return {"code": 0, "message": "领取成功", "data": _public_assignment(assignment)}


# ---------- 任务状态流转（管理端：上架/进行中/关闭） ----------

_TASK_STATUS_FLOW = {
    "open": {"inProgress", "closed"},
    "inProgress": {"open", "closed"},
    "closed": {"open"},
}
VALID_TASK_STATUS = {"open", "inProgress", "closed"}


@bp.post("/<int:task_id>/status")
@require_role("admin")
def set_task_status(task_id):
    """管理员变更任务状态（上架/进行中/关闭），仅改 status 字段；同状态幂等 no-op。"""
    task = db.session.get(Task, task_id)
    if not task:
        return {"code": 404, "message": "任务不存在"}, 404
    status = (request.get_json(silent=True) or {}).get("status")
    if status not in VALID_TASK_STATUS:
        return {"code": 400, "message": "status 无效"}, 400
    if status == task.status:
        return {"code": 0, "message": "ok", "data": _public_task(task)}  # 同状态幂等 no-op
    if status not in _TASK_STATUS_FLOW.get(task.status, set()):
        return {"code": 400, "message": f"不允许从 {task.status} 变更为 {status}"}, 400
    task.status = status
    db.session.commit()
    return {"code": 0, "message": "ok", "data": _public_task(task)}


# ---------- T3-6 作业提交（claimed -> submitted） ----------

@bp.post("/<int:task_id>/assignments/<int:assignment_id>/submit")
@login_required
def submit_assignment(task_id, assignment_id):
    """提交作业：仅本人已领取且处于 claimed 状态可提交。"""
    assignment = db.session.execute(
        db.select(Assignment).where(
            Assignment.id == assignment_id, Assignment.task_id == task_id
        )
    ).scalar_one_or_none()
    if not assignment:
        return {"code": 404, "message": "作业记录不存在"}, 404
    if assignment.openid != g.openid:
        return {"code": 403, "message": "无权操作他人作业"}, 403
    if assignment.status != "claimed":
        return {"code": 400, "message": f"当前状态 {assignment.status} 不可提交"}, 400

    assignment.status = "submitted"
    assignment.submit_time = datetime.utcnow()
    db.session.commit()
    return {"code": 0, "data": _public_assignment(assignment)}