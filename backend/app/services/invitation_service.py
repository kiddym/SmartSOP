"""用户邀请：invite(建邀请+发邮件) + accept(建用户+标记)。pre-auth accept 用 bypass。"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import security, tenant
from app.billing.catalog import effective_seat_limit
from app.errors import bad_request, conflict, payment_required
from app.models.base import utcnow
from app.models.company import Company
from app.models.role import Role
from app.models.user import User, UserStatus
from app.models.user_invitation import UserInvitation
from app.services import email_outbox_service

_TTL_DAYS = 7


def assert_seat_available(db: Session, company_id: str) -> None:
    """座席上限守卫：在职用户 + 未过期待处理邀请 >= 上限 → 402。无限套餐放行。"""
    company = db.get(Company, company_id)
    limit = effective_seat_limit(
        company.plan if company else None,
        company.subscription_status if company else None,
    )
    if limit is None:
        return
    active_users = db.execute(
        select(func.count())
        .select_from(User)
        .where(User.company_id == company_id, User.status == UserStatus.active)
    ).scalar_one()
    pending_invites = db.execute(
        select(func.count())
        .select_from(UserInvitation)
        .where(
            UserInvitation.company_id == company_id,
            UserInvitation.status == "pending",
            UserInvitation.expires_at > utcnow(),
        )
    ).scalar_one()
    if active_users + pending_invites >= limit:
        raise payment_required("SEAT_LIMIT_REACHED", "席位已达上限，请升级订阅以增加席位")


def assert_role_in_company(db: Session, company_id: str, role_id: str | None) -> None:
    """角色租户归属守卫：role_id 非空时必须属于本公司，否则 400。"""
    if role_id is None:
        return
    role = db.execute(
        select(Role).where(Role.id == role_id, Role.company_id == company_id)
    ).scalar_one_or_none()
    if role is None:
        raise bad_request("INVALID_ROLE", "角色不存在或不属于本组织")


def invite(
    db: Session, *, company_id: str, email: str, role_id: str | None, invited_by: str | None
) -> tuple[UserInvitation, str]:
    """建邀请 + 入队邀请邮件。返回 (invitation, 明文token)。明文仅供测试；路由不回传。"""
    existing = db.execute(
        select(User).where(User.company_id == company_id, User.email == email)
    ).scalar_one_or_none()
    if existing is not None:
        raise conflict("EMAIL_EXISTS", "该邮箱已是本组织成员")
    assert_seat_available(db, company_id)
    assert_role_in_company(db, company_id, role_id)
    company_obj = db.get(Company, company_id)
    company_name = company_obj.name if company_obj is not None else company_id
    raw = security.generate_token()
    inv = UserInvitation(
        company_id=company_id,
        email=email,
        role_id=role_id,
        token_hash=security.hash_token(raw),
        expires_at=utcnow() + timedelta(days=_TTL_DAYS),
        status="pending",
        invited_by=invited_by,
    )
    db.add(inv)
    db.flush()
    email_outbox_service.enqueue_transactional(
        db,
        company_id=company_id,
        recipient_email=email,
        type="INVITE_USER",
        params={
            "invite_url": f"/accept-invite?token={raw}",
            "company_name": company_name,
            "deadline": f"{_TTL_DAYS} 天后",
        },
    )
    db.flush()
    return inv, raw


def accept(db: Session, *, token: str, name: str, password: str) -> User:
    with tenant.bypass_tenant_scope():
        now = utcnow()
        inv = db.execute(
            select(UserInvitation).where(
                UserInvitation.token_hash == security.hash_token(token),
                UserInvitation.status == "pending",
                UserInvitation.expires_at > now,
            )
        ).scalar_one_or_none()
    if inv is None:
        raise bad_request("INVALID_TOKEN", "邀请链接无效或已过期")
    ctx = tenant.set_current_company_id(inv.company_id)
    try:
        dup = db.execute(
            select(User).where(User.company_id == inv.company_id, User.email == inv.email)
        ).scalar_one_or_none()
        if dup is not None:
            raise conflict("EMAIL_EXISTS", "该邮箱已是本组织成员")
        user = User(
            company_id=inv.company_id,
            email=inv.email,
            name=name,
            password_hash=security.hash_password(password),
            role_id=inv.role_id,
            status=UserStatus.active,
        )
        db.add(user)
        inv.status = "accepted"
        db.flush()
    finally:
        tenant.reset_current_company_id(ctx)
    return user
