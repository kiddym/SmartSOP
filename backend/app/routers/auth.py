"""Auth API (/api/v1/auth)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import security, tenant
from app.deps import get_db, get_current_user, _user_permission_codes
from app.errors import conflict, unauthorized
from app.models.role import Role
from app.models.user import User
from app.schemas.auth import (
    RegisterRequest, LoginRequest, RefreshRequest, TokenPair, CurrentUser,
)
from app.services import auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _role_code(db: Session, user: User) -> str | None:
    if user.role_id is None:
        return None
    role = db.get(Role, user.role_id)
    return role.code if role else None


def _tokens(db: Session, user: User) -> TokenPair:
    rc = _role_code(db, user)
    return TokenPair(
        access_token=security.create_access_token(
            user_id=user.id, company_id=user.company_id, role_code=rc),
        refresh_token=security.create_refresh_token(
            user_id=user.id, company_id=user.company_id, role_code=rc),
    )


@router.post("/register", response_model=TokenPair, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    try:
        user = auth_service.register(db, payload)
    except auth_service.AuthError as exc:
        raise conflict("COMPANY_EXISTS", str(exc))
    return _tokens(db, user)


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    try:
        user = auth_service.authenticate(db, payload)
    except auth_service.AuthError as exc:
        raise unauthorized("LOGIN_FAILED", str(exc))
    return _tokens(db, user)


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        claims = security.decode_token(payload.refresh_token)
    except security.TokenError:
        raise unauthorized("INVALID_TOKEN", "无效的令牌")
    if claims.get("type") != "refresh":
        raise unauthorized("INVALID_TOKEN", "令牌类型错误")
    tenant.set_current_company_id(claims.get("company_id"))
    user = db.get(User, claims.get("sub"))
    if user is None:
        raise unauthorized("USER_NOT_FOUND", "用户不存在")
    return _tokens(db, user)


@router.get("/me", response_model=CurrentUser)
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return CurrentUser(
        id=current_user.id, email=current_user.email, name=current_user.name,
        company_id=current_user.company_id, role_code=_role_code(db, current_user),
        permissions=sorted(_user_permission_codes(db, current_user)),
    )
