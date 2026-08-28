"""能力认证与准入考试接口（阶段三 T3-2）。

用户领取某类标注任务前需通过该任务该类型的准入考试：
- worker 提交考试记录（绑定 openid + task_id + annot_type，幂等唯一）。
- admin 评级：设置能力等级(level) 与是否通过(exam_passed)、复核人(reviewed_by)与时间。
认证等级用于领取时校验 require_level 满足任务最低等级。
"""
from datetime import datetime

from flask import Blueprint, g, request

from ..auth import login_required, require_role
from ..extensions import db
from ..models import Certification, Task, User

bp = Blueprint("certifications", __name__)

VALID_ANNOT = {"shadow", "light_source", "reflection", "exposure", "filter"}
VALID_LEVEL = {"junior", "middle", "senior"}


def _public_cert(cert):
    return {
        "id": cert.id,
        "openid": cert.openid,
        "task_id": cert.task_id,
        "task_name": cert.task_name,
        "annot_type": cert.annot_type,
        "level": cert.level,
        "exam_passed": cert.exam_passed,
        "pass_rate": str(cert.pass_rate) if cert.pass_rate is not None else None,
        "reviewed_by": cert.reviewed_by,
        "review_time": cert.review_time.isoformat() if cert.review_time else None,
    }


@bp.get("/mine")
@login_required
def mine():
    """worker 查看本人的认证记录。"""
    rows = db.session.execute(
        db.select(Certification)
        .where(Certification.openid == g.openid)
        .order_by(Certification.id.desc())
    ).scalars()
    return {"code": 0, "data": [_public_cert(c) for c in rows]}


@bp.post("")
@login_required
def submit_exam():
    """提交准入考试结果（同 openid+task+annot_type 重复提交视为更新）。

    body: { task_id, annot_type, pass_rate(0~100), exam_passed?(可选) }
    """
    body = request.get_json(silent=True) or {}
    task_id = body.get("task_id")
    annot_type = (body.get("annot_type") or "").strip()
    pass_rate = body.get("pass_rate")

    try:
        task_id = int(task_id)
    except (TypeError, ValueError):
        return {"code": 400, "message": "task_id 无效"}, 400
    if annot_type not in VALID_ANNOT:
        return {"code": 400, "message": "annot_type 无效"}, 400
    if pass_rate is None:
        exam_passed = False
    else:
        try:
            pass_rate = float(pass_rate)
        except (TypeError, ValueError):
            return {"code": 400, "message": "pass_rate 无效"}, 400
        if not (0 <= pass_rate <= 100):
            return {"code": 400, "message": "pass_rate 需在 0~100"}, 400
        exam_passed = bool(body.get("exam_passed", pass_rate >= 60))

    task = db.session.get(Task, task_id)
    if not task:
        return {"code": 404, "message": "任务不存在"}, 404

    cert = db.session.execute(
        db.select(Certification).where(
            Certification.openid == g.openid,
            Certification.task_id == task_id,
            Certification.annot_type == annot_type,
        )
    ).scalar_one_or_none()

    if cert:
        # 已存在：仅允许更新考试结果，评审状态由 admin 覆盖
        cert.pass_rate = pass_rate
        cert.exam_passed = exam_passed
    else:
        cert = Certification(
            openid=g.openid,
            task_id=task_id,
            task_name=task.title,
            annot_type=annot_type,
            pass_rate=pass_rate,
            exam_passed=exam_passed,
        )
        db.session.add(cert)
    db.session.commit()
    return {"code": 0, "data": _public_cert(cert)}


@bp.post("/<int:cert_id>/rate")
@require_role("admin")
def rate(cert_id):
    """管理端评级：设置能力等级与考试复核结果。

    body: { level?, exam_passed?, pass_rate?, reviewed_by? }
    """
    cert = db.session.get(Certification, cert_id)
    if not cert:
        return {"code": 404, "message": "认证记录不存在"}, 404

    body = request.get_json(silent=True) or {}
    level = (body.get("level") or "").strip()
    if level and level not in VALID_LEVEL:
        return {"code": 400, "message": "level 无效"}, 400
    if level:
        cert.level = level

    if "exam_passed" in body:
        cert.exam_passed = bool(body["exam_passed"])
    if "pass_rate" in body:
        pass_rate = body["pass_rate"]
        try:
            pass_rate = float(pass_rate)
        except (TypeError, ValueError):
            return {"code": 400, "message": "pass_rate 无效"}, 400
        if not (0 <= pass_rate <= 100):
            return {"code": 400, "message": "pass_rate 需在 0~100"}, 400
        cert.pass_rate = pass_rate

    cert.reviewed_by = g.openid
    cert.review_time = datetime.utcnow()
    db.session.commit()
    return {"code": 0, "data": _public_cert(cert)}


@bp.get("/list")
@require_role("admin")
def admin_list():
    """管理端：认证记录列表，可按任务/标注类型过滤（T5-4）。"""
    task_id = request.args.get("task_id")
    annot_type = (request.args.get("annot_type") or "").strip()
    q = db.select(Certification)
    if task_id:
        try:
            task_id = int(task_id)
        except (TypeError, ValueError):
            task_id = None
        if task_id:
            q = q.where(Certification.task_id == task_id)
    if annot_type:
        q = q.where(Certification.annot_type == annot_type)
    q = q.order_by(Certification.id.desc())
    rows = db.session.execute(q).scalars().all()
    openids = {c.openid for c in rows}
    users = (
        {
            u.openid: u
            for u in db.session.execute(
                db.select(User).where(User.openid.in_(openids))
            ).scalars()
        }
        if openids
        else {}
    )
    data = []
    for c in rows:
        item = _public_cert(c)
        item["user_name"] = users[c.openid].real_name if users.get(c.openid) else None
        data.append(item)
    return {"code": 0, "data": data}