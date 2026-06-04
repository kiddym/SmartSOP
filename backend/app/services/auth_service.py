"""Auth service: self-service registration (creates tenant) + login.

Pre-auth flows run with no tenant context, so cross-tenant lookups work.
register() sets context to the new company before seeding roles/user so the
isolation events stamp them correctly.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import security, tenant
from app.errors import bad_request
from app.models.company import Company
from app.models.role import Role
from app.models.user import User, UserStatus
from app.permissions import BUILTIN_ROLES
from app.schemas.auth import LoginRequest, RegisterRequest
from app.seed import seed_tenant_sop


class AuthError(Exception):
    """Registration or authentication failure."""


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return s or "company"


def create_company(db: Session, payload: RegisterRequest) -> User:
    """唯一建公司工厂：建 Company → 设上下文 → 播 roles/super_admin user → SOP seed。

    强制「新公司即有 SOP 系统数据」不变量——任何建公司路径（注册/未来管理台/导入）
    都须经此，禁止裸 `db.add(Company(...))` 绕过 seed 与上下文设定。
    返回新建的 super_admin User。
    """
    slug = _slugify(payload.company_name)
    with tenant.bypass_tenant_scope():
        if db.execute(select(Company).where(Company.slug == slug)).scalar_one_or_none():
            raise AuthError(f"公司标识已存在: {slug}")

    company = Company(name=payload.company_name, slug=slug)
    db.add(company)
    db.flush()  # assign company.id

    token = tenant.set_current_company_id(company.id)
    try:
        roles_by_code: dict[str, Role] = {}
        for spec in BUILTIN_ROLES:
            role = Role(
                code=spec["code"],
                name=spec["name"],
                is_builtin=True,
                permissions=list(spec["permissions"]),
            )
            db.add(role)
            roles_by_code[spec["code"]] = role
        db.flush()
        user = User(
            email=payload.email,
            password_hash=security.hash_password(payload.password),
            name=payload.name,
            role_id=roles_by_code["super_admin"].id,
            status=UserStatus.active,
        )
        db.add(user)
        db.flush()
        seed_tenant_sop(db)  # 每公司 SOP 系统数据（上下文已是新公司）
        db.commit()
        db.refresh(user)
        return user
    finally:
        tenant.reset_current_company_id(token)


def register(db: Session, payload: RegisterRequest) -> User:
    """自助注册：薄封装 create_company，保证注册的公司带齐 SOP seed。"""
    return create_company(db, payload)


def authenticate(db: Session, payload: LoginRequest) -> User:
    with tenant.bypass_tenant_scope():
        candidates = db.execute(select(User).where(User.email == payload.email)).scalars().all()
        if payload.company_slug:
            company = db.execute(
                select(Company).where(Company.slug == payload.company_slug)
            ).scalar_one_or_none()
            if company is None:
                raise AuthError("公司不存在")
            candidates = [u for u in candidates if u.company_id == company.id]

    if not candidates:
        raise AuthError("邮箱或密码错误")
    if len(candidates) > 1:
        raise AuthError("该邮箱存在于多个公司，请提供公司标识")
    user = candidates[0]
    if user.status != UserStatus.active:
        raise AuthError("账号已禁用")
    if not security.verify_password(payload.password, user.password_hash):
        raise AuthError("邮箱或密码错误")
    return user


def change_password(db: Session, user: User, old_password: str, new_password: str) -> None:
    if not security.verify_password(old_password, user.password_hash):
        raise bad_request("INVALID_CREDENTIALS", "原密码不正确")
    user.password_hash = security.hash_password(new_password)
    db.flush()
