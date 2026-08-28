"""外部核验结果回写接口（阶段三 T3-7）。

管理员在外部任务系统核验作业后，仅将结果回写本系统：
- 通过   → assignment 置 passed，记录核验人/核验时间/完成时间
- 未通过 → assignment 置 rejected，记录核验人/核验时间
同步写入 quality_checks 留痕（uk_qc_assignment 唯一索引防重复回写）。
佣金结算（commissions + balance）属阶段四，接口内不处理。
"""
from datetime import datetime

from flask import Blueprint, g, request
from sqlalchemy.exc import IntegrityError

from ..auth import require_role
from ..extensions import db
from ..models import Assignment, QualityCheck, Task, User
from .wallet import settle_commission

bp = Blueprint("quality", __name__)


def _public_qc(qc):
    return {
        "id": qc.id,
        "assignment_id": qc.assignment_id,
        "openid": qc.openid,
        "task_id": qc.task_id,
        "checked_by": qc.checked_by,
        "result": qc.result,
        "external_ref_no": qc.external_ref_no,
        "remark": qc.remark,
        "check_time": qc.check_time.isoformat() if qc.check_time else None,
    }


@bp.post("/writeback")
@require_role("admin")
def writeback():
    """外部核验结果回写。

    body: { assignment_id, result: pass|reject, external_ref_no?, remark?, task_id? }
    result 与核验单号必填当 result=pass 时 typical。assignment_id 必填。
    """
    body = request.get_json(silent=True) or {}
    assignment_id = body.get("assignment_id")
    result = (body.get("result") or "").strip()
    external_ref_no = (body.get("external_ref_no") or "").strip()
    remark = (body.get("remark") or "").strip()

    try:
        assignment_id = int(assignment_id)
    except (TypeError, ValueError):
        return {"code": 400, "message": "assignment_id 无效"}, 400
    if result not in ("pass", "reject"):
        return {"code": 400, "message": "result 需为 pass 或 reject"}, 400
    if result == "pass" and not external_ref_no:
        return {"code": 400, "message": "核验通过必须携带 external_ref_no"}, 400

    assignment = db.session.get(Assignment, assignment_id)
    if not assignment:
        return {"code": 404, "message": "作业不存在"}, 404
    if assignment.status != "submitted":
        return {"code": 400, "message": f"当前状态 {assignment.status} 不可核验，需先提交"}, 400

    # 幂等：同一作业只允许回写一次（唯一索引兜底）
    existed = db.session.execute(
        db.select(QualityCheck).where(QualityCheck.assignment_id == assignment_id)
    ).scalar_one_or_none()
    if existed:
        return {"code": 409, "message": "该作业已核验，请勿重复回写"}, 409

    now = datetime.utcnow()
    # 写入外部核验结果留痕
    qc = QualityCheck(
        assignment_id=assignment_id,
        openid=assignment.openid,
        task_id=assignment.task_id,
        checked_by=g.openid,
        result=result,
        external_ref_no=external_ref_no or None,
        remark=remark or None,
        check_time=now,
    )
    db.session.add(qc)
    # 更新作业状态
    assignment.status = "passed" if result == "pass" else "rejected"
    assignment.checked_by = g.openid
    assignment.audit_time = now
    # 阶段四 T4-1：核验通过即触发佣金入账（与回写同事务，assignment_id 唯一索引幂等）
    if result == "pass":
        task = db.session.get(Task, assignment.task_id)
        if task:
            quantity = body.get("submitted_quantity")
            if quantity in (None, ""):
                quantity = task.quantity
            settle_commission(assignment, task, quantity)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return {"code": 409, "message": "该作业已核验或将重复回写"}, 409
    return {"code": 0, "data": _public_qc(qc)}


@bp.get("/by-task/<int:task_id>")
@require_role("admin")
def list_by_task(task_id):
    """管理端：查看某任务下全部核验留痕。"""
    rows = db.session.execute(
        db.select(QualityCheck)
        .where(QualityCheck.task_id == task_id)
        .order_by(QualityCheck.id.desc())
    ).scalars()
    return {"code": 0, "data": [_public_qc(q) for q in rows]}


@bp.get("/pending-assignments")
@require_role("admin")
def pending_assignments():
    """管理端：待核验（submitted）作业列表，可指定核验人过滤（T5-3）。"""
    checked_by = (request.args.get("checked_by") or "").strip()
    q = db.select(Assignment).where(Assignment.status == "submitted")
    if checked_by:
        q = q.where(Assignment.checked_by == checked_by)
    q = q.order_by(Assignment.id.desc())
    assigns = db.session.execute(q).scalars().all()
    openids = {a.openid for a in assigns}
    users = {}
    if openids:
        users = {
            u.openid: u
            for u in db.session.execute(
                db.select(User).where(User.openid.in_(openids))
            ).scalars()
        }
    data = []
    for a in assigns:
        u = users.get(a.openid)
        data.append(
            {
                "assignment_id": a.id,
                "openid": a.openid,
                "user_name": u.real_name if u else None,
                "task_id": a.task_id,
                "task_name": a.task_name,
                "submit_time": a.submit_time.isoformat() if a.submit_time else None,
            }
        )
    return {"code": 0, "data": data}