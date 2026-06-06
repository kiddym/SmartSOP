"""切换账户授权关系（净室原创）：某 super 用户被授权切换进某公司。

注意：本表仅表示「授权切入」的白名单。实际切换仍须目标公司内存在同 email 的成员
账户（见 auth_service.switch_account），token 始终指向真实成员身份，不凭空越权。
company_id（TenantMixin）= 授权来源/super 用户所属公司；target_company_id = 可切入的目标公司。
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class SuperAccountRelation(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_super_account_relation"
    __table_args__ = (
        UniqueConstraint("super_user_id", "target_company_id", name="uq_super_account_relation"),
    )

    super_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_user.id", ondelete="CASCADE"), index=True
    )
    target_company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_company.id", ondelete="CASCADE"), index=True
    )
