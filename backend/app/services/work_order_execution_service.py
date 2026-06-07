"""SOP×工单执行服务：挂接已发布版本、生成执行行、执行视图、填 step、完成校验。

钉定即不可变：执行行用弱引用 node_id + 冗余 code/sort_order；input_schema 在
执行视图按需从钉定版本节点读取（版本不可变，安全）。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.errors import bad_request, conflict, not_found, unprocessable
from app.models.base import utcnow
from app.models.node import ProcedureNode
from app.models.procedure import Procedure
from app.models.work_order import WorkOrder
from app.models.work_order_status import WorkOrderStatus
from app.models.work_order_step_result import WorkOrderStepResult
from app.schemas.work_order import StepResultUpdate
from app.services import attachment_service
from app.services import work_order_service as wos


def list_step_results(db: Session, work_order_id: str) -> list[WorkOrderStepResult]:
    return list(
        db.execute(
            select(WorkOrderStepResult)
            .where(
                WorkOrderStepResult.work_order_id == work_order_id,
                WorkOrderStepResult.is_active.is_(True),
            )
            .order_by(WorkOrderStepResult.node_sort_order, WorkOrderStepResult.id)
        )
        .scalars()
        .all()
    )


def get_step_result(db: Session, result_id: str) -> WorkOrderStepResult | None:
    return db.execute(
        select(WorkOrderStepResult).where(
            WorkOrderStepResult.id == result_id,
            WorkOrderStepResult.is_active.is_(True),
        )
    ).scalar_one_or_none()


def _pinned_nodes(db: Session, procedure_id: str) -> list[ProcedureNode]:
    return list(
        db.execute(
            select(ProcedureNode)
            .where(ProcedureNode.procedure_id == procedure_id, ProcedureNode.is_active.is_(True))
            .order_by(ProcedureNode.sort_order, ProcedureNode.id)
        )
        .scalars()
        .all()
    )


def attach_procedure(
    db: Session, wo: WorkOrder, procedure_id: str, company_id: str, actor_user_id: str | None
) -> WorkOrder:
    if wo.procedure_id is not None:
        raise conflict("WORKORDER_PROCEDURE_ATTACHED", "工单已挂接 SOP，请先解绑")
    proc = db.get(Procedure, procedure_id)
    if proc is None or proc.company_id != company_id or not proc.is_active:
        raise not_found("PROCEDURE_NOT_FOUND", "程序不存在")
    if proc.status != "PUBLISHED":
        raise bad_request("PROCEDURE_NOT_PUBLISHED", "只能挂接已发布的程序")
    wo.procedure_id = proc.id
    wo.procedure_group_id = proc.procedure_group_id
    wo.procedure_attached_at = utcnow()
    for node in _pinned_nodes(db, proc.id):
        if node.kind != "step":
            continue
        db.add(
            WorkOrderStepResult(
                work_order_id=wo.id,
                node_id=node.id,
                node_code=node.code,
                node_sort_order=node.sort_order,
                response={},
                company_id=company_id,
            )
        )
    wos._log(db, wo.id, company_id, "SOP_ATTACH", actor_user_id=actor_user_id)
    db.commit()
    db.refresh(wo)
    return wo


def detach_procedure(db: Session, wo: WorkOrder, company_id: str) -> WorkOrder:
    if wo.status == WorkOrderStatus.COMPLETE:
        raise bad_request("WORKORDER_COMPLETE_LOCKED", "已完成工单不可解绑 SOP")
    # 先软删 step_result 的附件，避免孤儿附件残留至定时清理。
    rows = list(
        db.execute(
            select(WorkOrderStepResult).where(WorkOrderStepResult.work_order_id == wo.id)
        ).scalars()
    )
    attachment_service.soft_delete_for_entities(db, "work_order_step_result", [r.id for r in rows])
    db.execute(delete(WorkOrderStepResult).where(WorkOrderStepResult.work_order_id == wo.id))
    wo.procedure_id = None
    wo.procedure_group_id = None
    wo.procedure_attached_at = None
    db.commit()
    db.refresh(wo)
    return wo


def execution_view(db: Session, wo: WorkOrder) -> dict[str, Any]:
    if wo.procedure_id is None:
        return {"procedure": None, "outline": [], "steps": []}
    proc = db.get(Procedure, wo.procedure_id)
    nodes = _pinned_nodes(db, wo.procedure_id)
    schema_by_id = {n.id: (n.input_schema or {}) for n in nodes}
    outline = [
        {
            "node_id": n.id,
            "heading_level": n.heading_level,
            "kind": n.kind,
            "body": n.body,
            "code": n.code,
            "sort_order": n.sort_order,
        }
        for n in nodes
    ]
    sr_rows = list_step_results(db, wo.id)
    counts = attachment_service.count_active_by_entity_ids(
        db, "work_order_step_result", [r.id for r in sr_rows]
    )
    steps = []
    for sr in sr_rows:
        steps.append(
            {
                "id": sr.id,
                "node_id": sr.node_id,
                "node_code": sr.node_code,
                "node_sort_order": sr.node_sort_order,
                "input_schema": schema_by_id.get(sr.node_id, {}),
                "response": sr.response or {},
                "is_done": sr.is_done,
                "done_by_user_id": sr.done_by_user_id,
                "done_at": sr.done_at,
                "notes": sr.notes,
                "attachment_count": counts.get(sr.id, 0),
            }
        )
    procedure = None
    if proc is not None:
        procedure = {
            "id": proc.id,
            "group_id": proc.procedure_group_id,
            "code": proc.code,
            "name": proc.name,
            "version": proc.version,
        }
    return {"procedure": procedure, "outline": outline, "steps": steps}


ATTACHMENT_STEP_TYPES = frozenset({"UPLOAD", "PHOTO", "SIGNATURE"})


def _requires_attachment(db: Session, node_id: str) -> bool:
    """附件类型步骤且标记为必填时返回 True（type∈ATTACHMENT_STEP_TYPES 且 required truthy）。"""
    node = db.get(ProcedureNode, node_id)
    if node is None:
        return False
    schema = node.input_schema or {}
    return str(schema.get("type", "")).upper() in ATTACHMENT_STEP_TYPES and bool(
        schema.get("required")
    )


def _required_fields(db: Session, node_id: str) -> list[str]:
    node = db.get(ProcedureNode, node_id)
    if node is None:
        return []
    schema = node.input_schema or {}
    req = schema.get("required", [])
    return list(req) if isinstance(req, list) else []


def update_step(
    db: Session,
    wo: WorkOrder,
    sr: WorkOrderStepResult,
    payload: StepResultUpdate,
    company_id: str,
    actor_user_id: str | None,
) -> WorkOrderStepResult:
    if wo.status != WorkOrderStatus.IN_PROGRESS:
        raise bad_request("WORKORDER_NOT_IN_PROGRESS", "工单需处于执行中才能填写步骤")
    data = payload.model_dump(exclude_unset=True)
    if "response" in data and data["response"] is not None:
        sr.response = data["response"]
    if "notes" in data and data["notes"] is not None:
        sr.notes = data["notes"]
    if "is_done" in data and data["is_done"] is not None:
        if data["is_done"]:
            response = sr.response or {}
            missing = [
                f
                for f in _required_fields(db, sr.node_id)
                if f not in response or response[f] in (None, "")
            ]
            if missing:
                raise bad_request("STEP_REQUIRED_MISSING", "必填字段缺失", field=",".join(missing))
            if _requires_attachment(db, sr.node_id):
                count = attachment_service.count_active(db, "work_order_step_result", sr.id)
                if count == 0:
                    raise unprocessable(
                        "STEP_ATTACHMENT_REQUIRED",
                        "本步骤需上传附件后才能完成",
                    )
            sr.is_done = True
            sr.done_by_user_id = actor_user_id
            sr.done_at = utcnow()
            wos._log(
                db,
                wo.id,
                company_id,
                "STEP_DONE",
                actor_user_id=actor_user_id,
                comment=sr.node_code,
            )
        else:
            sr.is_done = False
            sr.done_by_user_id = None
            sr.done_at = None
    db.commit()
    db.refresh(sr)
    return sr


def assert_completable(db: Session, wo: WorkOrder) -> None:
    """转 COMPLETE 前置：若挂接 SOP，要求所有执行行已完成。"""
    if wo.procedure_id is None:
        return
    rows = list_step_results(db, wo.id)
    if any(not r.is_done for r in rows):
        raise bad_request("WORKORDER_STEPS_INCOMPLETE", "存在未完成的执行步骤")
