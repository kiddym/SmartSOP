"""FastAPI 依赖注入（Phase 1）。

提供数据库 session 与请求元信息（IP / UA / request_id），供 router 注入、
转交 service 用于审计写入。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app import security, tenant
from app.config import settings
from app.db import get_db
from app.errors import forbidden, unauthorized
from app.models.role import Role
from app.models.user import User, UserStatus
from app.permissions import effective_codes
from app.utils.net import extract_client_ip

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


@dataclass(frozen=True)
class RequestMeta:
    """单次请求的审计元信息。"""

    ip_address: str
    user_agent: str
    request_id: str


def get_request_meta(request: Request) -> RequestMeta:
    """提取真实客户端 IP（Q324）、UA、request_id，供审计日志使用。"""
    direct = request.client.host if request.client else ""
    xff = request.headers.get("x-forwarded-for")
    ip = extract_client_ip(direct, xff, settings.trusted_proxies)
    ua = request.headers.get("user-agent", "")
    rid = getattr(request.state, "request_id", "-")
    return RequestMeta(ip_address=ip[:45], user_agent=ua[:500], request_id=str(rid))


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not token:
        raise unauthorized("UNAUTHENTICATED", "未认证")
    try:
        claims = security.decode_token(token)
    except security.TokenError:
        raise unauthorized("INVALID_TOKEN", "无效的令牌") from None
    if claims.get("type") != "access":
        raise unauthorized("INVALID_TOKEN", "令牌类型错误")
    company_id = claims.get("company_id")
    user_id = claims.get("sub")
    tenant.set_current_company_id(company_id)  # scope before loading
    user = db.get(User, user_id)
    if user is None or user.company_id != company_id:
        raise unauthorized("USER_NOT_FOUND", "用户不存在")
    if user.status != UserStatus.active:
        raise unauthorized("ACCOUNT_DISABLED", "账号已禁用")
    return user


def user_permission_codes(db: Session, user: User) -> set[str]:
    role_code, stored = "", []
    if user.role_id is not None:
        role = db.get(Role, user.role_id)
        if role is not None:
            role_code, stored = role.code, (role.permissions or [])
    return effective_codes(role_code, stored)


def require_permission(code: str) -> Callable[[User, Session], User]:
    """Return a dependency enforcing the given permission code."""

    def checker(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if code not in user_permission_codes(db, current_user):
            raise forbidden("FORBIDDEN", "权限不足")
        return current_user

    return checker


__all__ = [
    "RequestMeta",
    "get_current_user",
    "get_db",
    "get_request_meta",
    "oauth2_scheme",
    "require_permission",
    "user_permission_codes",
]
