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
from app.billing.catalog import Feature, effective_features
from app.config import settings
from app.db import get_db
from app.errors import forbidden, payment_required, unauthorized
from app.models.company import Company
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
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    # 仅安全方法（GET/HEAD）允许用 access_token cookie 兜底，使浏览器 <img> 等
    # 无法携带 Authorization 头的资源请求可认证；写操作只认头，避免 CSRF。
    if not token and request.method in ("GET", "HEAD"):
        token = request.cookies.get("access_token")
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


def require_platform_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """仅平台运营身份（is_platform_admin）可通过。普通公司 super_admin 不可。"""
    if not current_user.is_platform_admin:
        raise forbidden("PLATFORM_ONLY", "仅平台管理员可操作")
    return current_user


def require_feature(feature: Feature) -> Callable[..., User]:
    """Return a dependency enforcing the company's plan includes the feature.

    与 require_permission 正交：super_admin 通配权限但不绕此闸门。
    订阅失效时 effective_features 已降级到 free，故自动锁高级模块。
    """

    def checker(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        company = db.get(Company, current_user.company_id)
        plan = company.plan if company else None
        status_ = company.subscription_status if company else None
        if feature not in effective_features(plan, status_):
            raise payment_required("FEATURE_LOCKED", "当前套餐未包含此功能，请升级订阅")
        return current_user

    return checker


__all__ = [
    "RequestMeta",
    "get_current_user",
    "get_db",
    "get_request_meta",
    "oauth2_scheme",
    "require_feature",
    "require_permission",
    "require_platform_admin",
    "user_permission_codes",
]
