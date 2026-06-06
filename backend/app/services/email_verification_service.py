"""邮箱验证（附加能力，仿密码重置）：request(认证用户给自己发验证邮件) + verify(校验置标记)。

email_verified 纯信息标记，不作登录门槛。token 单次、限时、只存哈希。
verify 走 bypass：token 是凭证、可在任意上下文兑付（与密码重置一致）。
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import security, tenant
from app.errors import bad_request
from app.models.base import utcnow
from app.models.user import User
from app.models.verification_token import VerificationToken
from app.services import email_outbox_service

_TTL_HOURS = 24


def request_verification(db: Session, user: User) -> str:
    """为当前用户生成验证 token 并入队验证邮件。返回明文 token（仅供测试；路由丢弃）。"""
    raw = security.generate_token()
    db.add(
        VerificationToken(
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
        type="EMAIL_VERIFICATION",
        params={"verify_url": f"/verify-email?token={raw}", "deadline": "24 小时"},
    )
    db.flush()
    return raw


def verify(db: Session, *, token: str) -> User:
    """校验 token 并置 user.email_verified=True。无效/过期/已用→400。"""
    with tenant.bypass_tenant_scope():
        now = utcnow()
        row = db.execute(
            select(VerificationToken).where(
                VerificationToken.token_hash == security.hash_token(token),
                VerificationToken.used_at.is_(None),
                VerificationToken.expires_at > now,
            )
        ).scalar_one_or_none()
        if row is None:
            raise bad_request("INVALID_TOKEN", "验证链接无效或已过期")
        user = db.get(User, row.user_id)
        if user is None:
            raise bad_request("INVALID_TOKEN", "验证链接无效或已过期")
        user.email_verified = True
        row.used_at = now
        db.flush()
        return user
