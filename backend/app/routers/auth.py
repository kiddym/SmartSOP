"""Auth API (/api/v1/auth)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app import security, tenant
from app.config import settings
from app.deps import get_current_user, get_db, user_permission_codes
from app.errors import conflict, unauthorized
from app.models.role import Role
from app.models.user import User, UserStatus
from app.schemas.auth import (
    ChangePasswordRequest,
    CurrentUser,
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SwitchableAccount,
    SwitchAccountRequest,
    TokenPair,
    VerifyEmailRequest,
)
from app.schemas.platform import AcceptInviteRequest
from app.services import (
    auth_service,
    email_verification_service,
    invitation_service,
    password_reset_service,
)

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
            user_id=user.id, company_id=user.company_id, role_code=rc
        ),
        refresh_token=security.create_refresh_token(
            user_id=user.id, company_id=user.company_id, role_code=rc
        ),
    )


def _issue(db: Session, user: User, response: Response) -> TokenPair:
    pair = _tokens(db, user)
    response.set_cookie(
        "access_token",
        pair.access_token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        path="/api/v1",
    )
    return pair


@router.post("/register", response_model=TokenPair, status_code=201)
def register(
    payload: RegisterRequest, response: Response, db: Session = Depends(get_db)
) -> TokenPair:
    try:
        user = auth_service.register(db, payload)
    except auth_service.AuthError as exc:
        raise conflict("COMPANY_EXISTS", str(exc)) from exc
    return _issue(db, user, response)


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> TokenPair:
    try:
        user = auth_service.authenticate(db, payload)
    except auth_service.AuthError as exc:
        raise unauthorized("LOGIN_FAILED", str(exc)) from exc
    return _issue(db, user, response)


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, response: Response, db: Session = Depends(get_db)) -> TokenPair:
    try:
        claims = security.decode_token(payload.refresh_token)
    except security.TokenError:
        raise unauthorized("INVALID_TOKEN", "无效的令牌") from None
    if claims.get("type") != "refresh":
        raise unauthorized("INVALID_TOKEN", "令牌类型错误")
    tenant.set_current_company_id(claims.get("company_id"))
    user = db.get(User, claims.get("sub"))
    if user is None:
        raise unauthorized("USER_NOT_FOUND", "用户不存在")
    if user.status != UserStatus.active:
        raise unauthorized("ACCOUNT_DISABLED", "账号已禁用")
    return _issue(db, user, response)


@router.post("/forgot-password", status_code=200)
def forgot_password(
    payload: ForgotPasswordRequest, db: Session = Depends(get_db)
) -> dict[str, str]:
    password_reset_service.request_reset(db, email=payload.email, company_slug=payload.company_slug)
    db.commit()
    return {"status": "ok"}  # 总 200，防枚举


@router.post("/reset-password", status_code=200)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    password_reset_service.reset(db, token=payload.token, new_password=payload.new_password)
    db.commit()
    return {"status": "ok"}


@router.post("/change-password", status_code=200)
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    auth_service.change_password(db, current_user, payload.old_password, payload.new_password)
    db.commit()
    return {"status": "ok"}


@router.post("/accept-invite", response_model=TokenPair)
def accept_invite(
    payload: AcceptInviteRequest, response: Response, db: Session = Depends(get_db)
) -> TokenPair:
    user = invitation_service.accept(
        db, token=payload.token, name=payload.name, password=payload.password
    )
    db.commit()
    return _issue(db, user, response)


@router.get("/switchable-accounts", response_model=list[SwitchableAccount])
def switchable_accounts(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[SwitchableAccount]:
    """当前用户可切入的公司列表。普通用户返回空列表。"""
    return auth_service.list_switchable_accounts(db, current_user)


@router.post("/switch-account", response_model=TokenPair)
def switch_account(
    payload: SwitchAccountRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TokenPair:
    """切换到目标公司的同 email 成员账户，签发指向该真实成员身份的 token。"""
    member = auth_service.switch_account(db, current_user, payload.company_id)
    tenant.set_current_company_id(member.company_id)
    return _issue(db, member, response)


@router.post("/request-verification", status_code=200)
def request_verification(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict[str, str]:
    """认证用户请求给自己发送邮箱验证邮件（落 outbox）。"""
    email_verification_service.request_verification(db, current_user)
    db.commit()
    return {"status": "ok"}


@router.post("/verify-email", status_code=200)
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    """校验邮箱验证 token，置 email_verified=True。无需认证（token 即凭证）。"""
    email_verification_service.verify(db, token=payload.token)
    db.commit()
    return {"status": "ok"}


@router.get("/me", response_model=CurrentUser)
def me(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> CurrentUser:
    return CurrentUser(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        company_id=current_user.company_id,
        role_code=_role_code(db, current_user),
        permissions=sorted(user_permission_codes(db, current_user)),
        email_verified=current_user.email_verified,
    )
