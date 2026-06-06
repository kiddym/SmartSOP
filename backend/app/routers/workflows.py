"""工作流 API（/api/v1/workflows）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.user import User
from app.models.workflow import Workflow
from app.schemas.workflow import WorkflowCreate, WorkflowRead, WorkflowUpdate
from app.services import workflow_service as svc

router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])


def _ensure(wf: Workflow | None, company_id: str) -> Workflow:
    if wf is None or wf.company_id != company_id:
        raise not_found("WORKFLOW_NOT_FOUND", "工作流不存在")
    return wf


@router.get("", response_model=list[WorkflowRead])
def list_workflows(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORKFLOW_VIEW)),
) -> list[Workflow]:
    return svc.list_workflows(db)


@router.post("", response_model=WorkflowRead, status_code=status.HTTP_201_CREATED)
def create_workflow(
    payload: WorkflowCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORKFLOW_MANAGE)),
) -> Workflow:
    return svc.create_workflow(db, payload, current_user.company_id)


@router.get("/{workflow_id}", response_model=WorkflowRead)
def get_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORKFLOW_VIEW)),
) -> Workflow:
    return _ensure(svc.get_workflow(db, workflow_id), current_user.company_id)


@router.patch("/{workflow_id}", response_model=WorkflowRead)
def update_workflow(
    workflow_id: str,
    payload: WorkflowUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORKFLOW_MANAGE)),
) -> Workflow:
    wf = _ensure(svc.get_workflow(db, workflow_id), current_user.company_id)
    return svc.update_workflow(db, wf, payload)


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.WORKFLOW_MANAGE)),
) -> None:
    wf = _ensure(svc.get_workflow(db, workflow_id), current_user.company_id)
    svc.delete_workflow(db, wf)
