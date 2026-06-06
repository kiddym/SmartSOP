"""工作流引擎：工单触发的规则评估与动作应用。

入口 ``run_for_work_order``：查该 company 下 enabled 且 trigger 匹配的 workflow，
逐条评估 conditions（针对该工单当前字段），匹配则按 actions 修改工单字段。

递归保护：动作中的 ``set_status`` 直接改 ``wo.status`` 字段（不走
``work_order_service.transition``），因此**不会**再触发 WORK_ORDER_STATUS_CHANGED
工作流。引擎仅由工单创建/状态转换的外层各调用一次，引擎内部绝不回调引擎或
transition，从根上杜绝无限递归。

跨租户校验：set_category 的目标分类、set_assignee_user 的目标用户、set_team
的目标团队均须属同一 company 且活跃，否则跳过该动作（不报错）。

本引擎只改内存中的 wo（及关联指派），不 commit；commit 由外层调用方负责，
保证与触发动作同事务。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.team import Team
from app.models.user import User, UserStatus
from app.models.work_order import WorkOrder, WorkOrderAssignee, WorkOrderTeam
from app.models.work_order_category import WorkOrderCategory
from app.models.work_order_status import WorkOrderPriority, WorkOrderStatus
from app.models.workflow import Workflow

# trigger 常量（与 schema.WorkflowTrigger 同值，引擎层避免反向依赖 schema）
WORK_ORDER_CREATED = "WORK_ORDER_CREATED"
WORK_ORDER_STATUS_CHANGED = "WORK_ORDER_STATUS_CHANGED"


def _wo_field_value(wo: WorkOrder, field: str) -> str | None:
    """取工单字段的可比较字符串值（enum 取 .value）。"""
    if field == "status":
        return wo.status.value
    if field == "priority":
        return wo.priority.value
    if field == "category_id":
        return wo.category_id
    return None


def _matches(wo: WorkOrder, conditions: list[dict[str, Any]]) -> bool:
    """全部条件满足才匹配；空列表=无条件总匹配。"""
    for cond in conditions:
        field = cond.get("field")
        op = cond.get("op")
        expected = cond.get("value")
        actual = _wo_field_value(wo, str(field)) if field is not None else None
        if op == "eq" and actual != expected:
            return False
        if op == "ne" and actual == expected:
            return False
    return True


def _apply_action(db: Session, wo: WorkOrder, action: dict[str, Any], company_id: str) -> None:
    """应用单个动作；非法目标（跨租户/不存在/已停用）静默跳过。"""
    a_type = action.get("type")
    value = action.get("value")

    if a_type == "set_priority":
        if value in {p.value for p in WorkOrderPriority}:
            wo.priority = WorkOrderPriority(value)
        return

    if a_type == "set_status":
        if value in {s.value for s in WorkOrderStatus}:
            # 直接改字段，绕过 transition，杜绝递归触发 STATUS_CHANGED 工作流。
            wo.status = WorkOrderStatus(value)
        return

    if a_type == "set_category":
        if value is None:
            wo.category_id = None
            return
        cat = db.get(WorkOrderCategory, value)
        if cat is not None and cat.is_active and cat.company_id == company_id:
            wo.category_id = value
        return

    if a_type == "set_assignee_user":
        if value is None:
            return
        user = db.get(User, value)
        if user is None or user.company_id != company_id or user.status == UserStatus.disabled:
            return
        exists = db.execute(
            select(WorkOrderAssignee).where(
                WorkOrderAssignee.work_order_id == wo.id,
                WorkOrderAssignee.user_id == value,
            )
        ).scalar_one_or_none()
        if exists is None:
            db.add(WorkOrderAssignee(work_order_id=wo.id, user_id=value, company_id=company_id))
        return

    if a_type == "set_team":
        if value is None:
            return
        team = db.get(Team, value)
        if team is None or not team.is_active or team.company_id != company_id:
            return
        team_exists = db.execute(
            select(WorkOrderTeam).where(
                WorkOrderTeam.work_order_id == wo.id,
                WorkOrderTeam.team_id == value,
            )
        ).scalar_one_or_none()
        if team_exists is None:
            db.add(WorkOrderTeam(work_order_id=wo.id, team_id=value, company_id=company_id))
        return


def run_for_work_order(db: Session, wo: WorkOrder, trigger: str, company_id: str) -> bool:
    """评估并应用该 company 下匹配 trigger 的工作流到工单 wo。

    返回是否有任一动作被应用（仅作信号；不 commit）。引擎不递归、不调用
    transition，故 set_status 动作不会触发新一轮 STATUS_CHANGED 工作流。
    """
    workflows = list(
        db.execute(
            select(Workflow)
            .where(
                Workflow.company_id == company_id,
                Workflow.enabled.is_(True),
                Workflow.trigger == trigger,
            )
            .order_by(Workflow.created_at, Workflow.id)
        )
        .scalars()
        .all()
    )
    applied = False
    for wf in workflows:
        conditions = wf.conditions or []
        actions = wf.actions or []
        if not _matches(wo, conditions):
            continue
        for action in actions:
            _apply_action(db, wo, action, company_id)
            applied = True
    return applied


__all__ = [
    "WORK_ORDER_CREATED",
    "WORK_ORDER_STATUS_CHANGED",
    "run_for_work_order",
]
