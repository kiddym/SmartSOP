"""Role management service (tenant-scoped; company_id passed explicitly)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.role import Role
from app.schemas.role import RoleCreate, RoleUpdate


def create_role(db: Session, payload: RoleCreate, company_id: str) -> Role:
    role = Role(
        code=payload.code,
        name=payload.name,
        is_builtin=False,
        permissions=payload.permissions,
        company_id=company_id,
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


def list_roles(db: Session) -> list[Role]:
    return list(db.execute(select(Role)).scalars().all())


def get_role(db: Session, role_id: str) -> Role | None:
    return db.get(Role, role_id)


def update_role(db: Session, role_id: str, payload: RoleUpdate) -> Role | None:
    role = db.get(Role, role_id)
    if role is None:
        return None
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(role, k, v)
    db.commit()
    db.refresh(role)
    return role


def delete_role(db: Session, role_id: str) -> None:
    role = db.get(Role, role_id)
    if role:
        db.delete(role)
        db.commit()
