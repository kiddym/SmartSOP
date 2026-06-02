"""密码重置：forgot(防枚举入队) + reset(校验 token 改密)。pre-auth 用 bypass。"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import security, tenant
from app.errors import bad_request
from app.models.base import utcnow
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User, UserStatus
from app.services import email_outbox_service

_TTL_HOURS = 1


def _find_user(db: Session, email: str, company_slug: str | None) -> User | None:
    stmt = select(User).where(User.email == email, User.status == UserStatus.active)
    if company_slug:
        from app.models.company import Company

        stmt = stmt.join(Company, Company.id == User.company_id).where(Company.slug == company_slug)
    # email 仅在公司内唯一；未带 company_slug 时同邮箱可能跨多公司存在。此处有意取首条
    # （而非像登录那样要求公司标识）——防枚举优先于精确定位，误发的重置邮件仍单次+1h 过期，危害低。
    return db.execute(stmt).scalars().first()


def request_reset(db: Session, *, email: str, company_slug: str | None = None) -> str | None:
    """生成重置 token 并入队邮件。返回明文 token（仅供测试；路由丢弃）。无此用户→None(防枚举)。"""
    with tenant.bypass_tenant_scope():
        user = _find_user(db, email, company_slug)
        if user is None:
            return None
        raw = security.generate_token()
        db.add(
            PasswordResetToken(
                user_id=user.id,
                company_id=user.company_id,
                token_hash=security.hash_token(raw),
                expires_at=utcnow() + timedelta(hours=_TTL_HOURS),
            )
        )
        email_outbox_service.enqueue_transactional(
            db,
            company_id=user.company_id,
            recipient_email=user.email,
            recipient_user_id=user.id,
            type="PASSWORD_RESET",
            params={"reset_url": f"/reset-password?token={raw}", "deadline": "1 小时"},
        )
        db.flush()
    return raw


def reset(db: Session, *, token: str, new_password: str) -> None:
    with tenant.bypass_tenant_scope():
        now = utcnow()
        row = db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == security.hash_token(token),
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.expires_at > now,
            )
        ).scalar_one_or_none()
        if row is None:
            raise bad_request("INVALID_TOKEN", "重置链接无效或已过期")
        user = db.get(User, row.user_id)
        if user is None:
            raise bad_request("INVALID_TOKEN", "重置链接无效或已过期")
        user.password_hash = security.hash_password(new_password)
        row.used_at = now
        db.flush()
