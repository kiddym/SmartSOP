"""User management service (tenant-scoped via ORM events)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import security
from app.models.user import User, UserStatus
from app.schemas.user import SelfProfileUpdate, UserCreate, UserUpdate
from app.services import invitation_service


def create_user(db: Session, payload: UserCreate, company_id: str | None = None) -> User:
    # company_id is stamped explicitly from the authenticated caller's tenant.
    # The before_flush isolation event would normally stamp it from the request
    # context, but a sync FastAPI dependency's contextvar mutation does not
    # propagate into the sync endpoint's separate threadpool task, so we pass it
    # through to guarantee the NOT-NULL tb_user.company_id is set.
    if company_id is not None:
        invitation_service.assert_seat_available(db, company_id)
        invitation_service.assert_role_in_company(db, company_id, payload.role_id)
    user = User(
        email=payload.email,
        password_hash=security.hash_password(payload.password),
        name=payload.name,
        role_id=payload.role_id,
        phone=payload.phone,
        job_title=payload.job_title,
        rate=payload.rate,
        avatar_url=payload.avatar_url,
        company_id=company_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def list_users(db: Session) -> list[User]:
    return list(db.execute(select(User)).scalars().all())


def get_user(db: Session, user_id: str) -> User | None:
    return db.get(User, user_id)


def update_user(db: Session, user_id: str, payload: UserUpdate) -> User | None:
    user = db.get(User, user_id)
    if user is None:
        return None
    data = payload.model_dump(exclude_unset=True)
    if "password" in data:
        user.password_hash = security.hash_password(data.pop("password"))
    for k, v in data.items():
        setattr(user, k, v)
    db.commit()
    db.refresh(user)
    return user


def update_self(db: Session, user: User, payload: SelfProfileUpdate) -> User:
    # Self-service edit: only the whitelisted profile fields on the schema are
    # applied. role_id/status/rate are not declared there and cannot be set.
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(user, k, v)
    db.commit()
    db.refresh(user)
    return user


def set_status(db: Session, user: User, status: UserStatus) -> User:
    user.status = status
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user_id: str) -> None:
    user = db.get(User, user_id)
    if user:
        db.delete(user)
        db.commit()
