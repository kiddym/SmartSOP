"""统一节点路由(spec §4)。Router 提交事务。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy.orm import Session

from app.deps import get_db
from app.schemas.node import (
    NodeBatchIn,
    NodeCreateIn,
    NodeOut,
    NodePatchIn,
    NodeReorderIn,
)
from app.services import node_service, optimistic_lock

# 不设共享 prefix:端点横跨两套 URL 层级(/api/v1/procedures/{id}/nodes 与 /api/v1/nodes/{id})。
router = APIRouter(tags=["nodes"])


def _changes_from_patch(payload: NodePatchIn) -> dict[str, Any]:
    changes: dict[str, Any] = {}
    if payload.set_heading_level:
        changes["heading_level"] = payload.heading_level
    if payload.kind is not None:
        changes["kind"] = payload.kind
    if payload.body is not None:
        changes["body"] = payload.body
    if payload.input_schema is not None:
        changes["input_schema"] = payload.input_schema
    if payload.attachment_marks is not None:
        changes["attachment_marks"] = payload.attachment_marks
    if payload.skip_numbering is not None:
        changes["skip_numbering"] = payload.skip_numbering
    return changes


@router.get("/api/v1/procedures/{procedure_id}/nodes", response_model=list[NodeOut])
def list_nodes(procedure_id: str, db: Session = Depends(get_db)) -> list[NodeOut]:
    return [NodeOut(**r) for r in node_service.get_nodes(db, procedure_id)]


@router.patch("/api/v1/nodes/{node_id}", response_model=NodeOut)
def patch_node(
    node_id: str,
    payload: NodePatchIn,
    db: Session = Depends(get_db),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> NodeOut:
    expected = optimistic_lock.ensure_if_match(if_match)
    node_service.patch_node(
        db, node_id, _changes_from_patch(payload), expected_revision=expected
    )
    db.commit()
    return NodeOut(**_one(db, node_id))


@router.post(
    "/api/v1/procedures/{procedure_id}/nodes",
    response_model=NodeOut,
    status_code=status.HTTP_201_CREATED,
)
def create_node(
    procedure_id: str, payload: NodeCreateIn, db: Session = Depends(get_db)
) -> NodeOut:
    created = node_service.create_node(db, procedure_id, payload.model_dump())
    db.commit()
    return NodeOut(**_one(db, created.id))


@router.delete("/api/v1/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_node(node_id: str, db: Session = Depends(get_db)) -> Response:
    node_service.delete_node(db, node_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/api/v1/procedures/{procedure_id}/nodes:batch", response_model=list[NodeOut])
def batch_update(
    procedure_id: str, payload: NodeBatchIn, db: Session = Depends(get_db)
) -> list[NodeOut]:
    updates: dict[str, dict[str, Any]] = {}
    for nid, item in payload.updates.items():
        changes: dict[str, Any] = {}
        if item.set_heading_level:
            changes["heading_level"] = item.heading_level
        if item.kind is not None:
            changes["kind"] = item.kind
        if item.input_schema is not None:
            changes["input_schema"] = item.input_schema
        if item.skip_numbering is not None:
            changes["skip_numbering"] = item.skip_numbering
        updates[nid] = changes
    node_service.batch_update(db, procedure_id, updates)
    db.commit()
    return [NodeOut(**r) for r in node_service.get_nodes(db, procedure_id)]


@router.post(
    "/api/v1/procedures/{procedure_id}/nodes/reorder",
    status_code=status.HTTP_204_NO_CONTENT,
)
def reorder(
    procedure_id: str, payload: NodeReorderIn, db: Session = Depends(get_db)
) -> Response:
    node_service.reorder(db, procedure_id, payload.ordered_ids)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _one(db: Session, node_id: str) -> dict[str, Any]:
    # 复用 node_service._get_node 取 procedure_id,再经 get_nodes 拿派生字段;
    # 待 Plan B 提供公共单节点访问器后可替换(见 code review 备注)。
    node = node_service._get_node(db, node_id)
    rows = node_service.get_nodes(db, node.procedure_id)
    for r in rows:
        if r["id"] == node_id:
            return r
    raise RuntimeError("node disappeared after write")
