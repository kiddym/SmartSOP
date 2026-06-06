"""Workflow 服务：CRUD（硬删，无软删 Mixin）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.workflow import Workflow
from app.schemas.workflow import WorkflowAction, WorkflowCondition, WorkflowCreate, WorkflowUpdate


def _dump_conditions(payload_conditions: list[WorkflowCondition]) -> list[dict[str, Any]]:
    return [c.model_dump(mode="json") for c in payload_conditions]


def _dump_actions(payload_actions: list[WorkflowAction]) -> list[dict[str, Any]]:
    return [a.model_dump(mode="json") for a in payload_actions]


def create_workflow(db: Session, payload: WorkflowCreate, company_id: str) -> Workflow:
    wf = Workflow(
        name=payload.name,
        enabled=payload.enabled,
        trigger=payload.trigger.value,
        conditions=_dump_conditions(payload.conditions),
        actions=_dump_actions(payload.actions),
        company_id=company_id,
    )
    db.add(wf)
    db.commit()
    db.refresh(wf)
    return wf


def list_workflows(db: Session) -> list[Workflow]:
    return list(
        db.execute(select(Workflow).order_by(Workflow.created_at, Workflow.id)).scalars().all()
    )


def get_workflow(db: Session, workflow_id: str) -> Workflow | None:
    return db.get(Workflow, workflow_id)


def update_workflow(db: Session, wf: Workflow, payload: WorkflowUpdate) -> Workflow:
    data = payload.model_dump(exclude_unset=True)
    if "name" in data:
        wf.name = data["name"]
    if "enabled" in data:
        wf.enabled = data["enabled"]
    if "trigger" in data and data["trigger"] is not None:
        wf.trigger = payload.trigger.value  # type: ignore[union-attr]
    if "conditions" in data and payload.conditions is not None:
        wf.conditions = _dump_conditions(payload.conditions)
    if "actions" in data and payload.actions is not None:
        wf.actions = _dump_actions(payload.actions)
    db.commit()
    db.refresh(wf)
    return wf


def delete_workflow(db: Session, wf: Workflow) -> None:
    db.delete(wf)
    db.commit()
