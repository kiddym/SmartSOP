"""Role management API (/api/v1/roles)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import permissions, tenant
from app.deps import get_db, require_permission
from app.errors import not_found, bad_request
from app.models.role import Role
from app.models.user import User
from app.schemas.role import RoleCreate, RoleRead, RoleUpdate
from app.services import role_service

router = APIRouter(prefix="/api/v1/roles", tags=["roles"])


def _ensure_same_tenant(role: Role | None, company_id: str) -> Role:
    if role is None or role.company_id != company_id:
        raise not_found("ROLE_NOT_FOUND", "角色不存在")
    return role


@router.get("", response_model=list[RoleRead])
def list_roles(db: Session = Depends(get_db),
               current_user: User = Depends(require_permission(permissions.ROLE_VIEW))):
    tenant.set_current_company_id(current_user.company_id)
    return role_service.list_roles(db)


@router.post("", response_model=RoleRead, status_code=201)
def create_role(payload: RoleCreate, db: Session = Depends(get_db),
                current_user: User = Depends(require_permission(permissions.ROLE_MANAGE))):
    tenant.set_current_company_id(current_user.company_id)
    return role_service.create_role(db, payload, current_user.company_id)


@router.patch("/{role_id}", response_model=RoleRead)
def update_role(role_id: str, payload: RoleUpdate, db: Session = Depends(get_db),
                current_user: User = Depends(require_permission(permissions.ROLE_MANAGE))):
    _ensure_same_tenant(role_service.get_role(db, role_id), current_user.company_id)
    return role_service.update_role(db, role_id, payload)


@router.delete("/{role_id}", status_code=204)
def delete_role(role_id: str, db: Session = Depends(get_db),
                current_user: User = Depends(require_permission(permissions.ROLE_MANAGE))):
    role = _ensure_same_tenant(role_service.get_role(db, role_id), current_user.company_id)
    if role.is_builtin:
        raise bad_request("ROLE_BUILTIN", "内置角色不可删除")
    role_service.delete_role(db, role_id)
