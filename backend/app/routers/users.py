"""User management API (/api/v1/users)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.errors import not_found
from app.models.user import User
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services import user_service

router = APIRouter(prefix="/api/v1/users", tags=["users"])


def _ensure_same_tenant(obj: User | None, company_id: str) -> User:
    # Tenant context is set by TenantContextMiddleware (scoped reads filter by
    # company). db.get() bypasses that scope, so this guard backs up
    # primary-key fetches against cross-tenant access.
    if obj is None or obj.company_id != company_id:
        raise not_found("USER_NOT_FOUND", "用户不存在")
    return obj


@router.post("", response_model=UserRead, status_code=201)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.USER_CREATE)),
) -> User:
    return user_service.create_user(db, payload, current_user.company_id)


@router.get("", response_model=list[UserRead])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.USER_VIEW)),
) -> list[User]:
    return user_service.list_users(db)


@router.get("/{user_id}", response_model=UserRead)
def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.USER_VIEW)),
) -> User:
    return _ensure_same_tenant(user_service.get_user(db, user_id), current_user.company_id)


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: str,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.USER_EDIT)),
) -> User | None:
    _ensure_same_tenant(user_service.get_user(db, user_id), current_user.company_id)
    return user_service.update_user(db, user_id, payload)


@router.delete("/{user_id}", status_code=204, response_model=None)
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(permissions.USER_DELETE)),
) -> None:
    _ensure_same_tenant(user_service.get_user(db, user_id), current_user.company_id)
    user_service.delete_user(db, user_id)
