"""维修请求 API（/api/v1/requests，含审批转工单）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.request import Request
from app.models.request_activity import RequestActivity
from app.models.request_status import RequestStatus
from app.models.user import User
from app.schemas.request import (
    ActivityRead,
    CommentCreate,
    RequestApprove,
    RequestCreate,
    RequestRead,
    RequestReason,
    RequestUpdate,
)
from app.services import request_service as svc

router = APIRouter(prefix="/api/v1/requests", tags=["requests"])


def _ensure(r: Request | None, company_id: str) -> Request:
    if r is None or r.company_id != company_id:
        raise not_found("REQUEST_NOT_FOUND", "请求不存在")
    return r


@router.get("", response_model=list[RequestRead])
def list_requests(
    status: str | None = None,
    priority: str | None = None,
    asset_id: str | None = None,
    location_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.REQUEST_VIEW)),
) -> list[Request]:
    return svc.list_requests(
        db, status=status, priority=priority, asset_id=asset_id, location_id=location_id
    )


@router.get("/pending", response_model=list[RequestRead])
def list_pending(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.REQUEST_VIEW)),
) -> list[Request]:
    return svc.list_requests(db, status=RequestStatus.PENDING.value)


@router.post("", response_model=RequestRead, status_code=status.HTTP_201_CREATED)
def create_request(
    payload: RequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.REQUEST_CREATE)),
) -> Request:
    return svc.create_request(db, payload, current_user.company_id, actor_user_id=current_user.id)


@router.get("/{request_id}", response_model=RequestRead)
def get_request(
    request_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.REQUEST_VIEW)),
) -> Request:
    return _ensure(svc.get_request(db, request_id), current_user.company_id)


@router.patch("/{request_id}", response_model=RequestRead)
def update_request(
    request_id: str,
    payload: RequestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.REQUEST_CREATE)),
) -> Request:
    r = _ensure(svc.get_request(db, request_id), current_user.company_id)
    return svc.update_request(db, r, payload)


@router.delete("/{request_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_request(
    request_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.REQUEST_DELETE)),
) -> None:
    r = _ensure(svc.get_request(db, request_id), current_user.company_id)
    svc.delete_request(db, r)


@router.post("/{request_id}/approve", response_model=RequestRead)
def approve_request(
    request_id: str,
    payload: RequestApprove,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.REQUEST_APPROVE)),
) -> Request:
    r = _ensure(svc.get_request(db, request_id), current_user.company_id)
    svc.approve_request(db, r, payload, current_user.company_id, actor_user_id=current_user.id)
    return r


@router.post("/{request_id}/reject", response_model=RequestRead)
def reject_request(
    request_id: str,
    payload: RequestReason,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.REQUEST_APPROVE)),
) -> Request:
    r = _ensure(svc.get_request(db, request_id), current_user.company_id)
    return svc.reject_request(
        db, r, payload.reason, current_user.company_id, actor_user_id=current_user.id
    )


@router.post("/{request_id}/cancel", response_model=RequestRead)
def cancel_request(
    request_id: str,
    payload: RequestReason,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.REQUEST_CANCEL)),
) -> Request:
    r = _ensure(svc.get_request(db, request_id), current_user.company_id)
    return svc.cancel_request(
        db, r, payload.reason, current_user.company_id, actor_user_id=current_user.id
    )


@router.get("/{request_id}/activities", response_model=list[ActivityRead])
def list_activities(
    request_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.REQUEST_VIEW)),
) -> list[RequestActivity]:
    _ensure(svc.get_request(db, request_id), current_user.company_id)
    return svc.list_activities(db, request_id)


@router.post(
    "/{request_id}/activities", response_model=ActivityRead, status_code=status.HTTP_201_CREATED
)
def add_comment(
    request_id: str,
    payload: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.REQUEST_VIEW)),
) -> RequestActivity:
    r = _ensure(svc.get_request(db, request_id), current_user.company_id)
    return svc.add_comment(
        db, r, payload.comment, current_user.company_id, actor_user_id=current_user.id
    )
