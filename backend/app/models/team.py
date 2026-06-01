"""团队及其成员（每租户）。成员关系用显式关联类，便于租户作用域。"""

from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin, UUIDMixin


class Team(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_team"
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_team_company_name"),)

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")


class TeamUser(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """团队↔用户成员关系。"""

    __tablename__ = "tb_team_user"
    __table_args__ = (UniqueConstraint("team_id", "user_id", name="uq_team_user"),)

    team_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_team.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_user.id", ondelete="CASCADE"), index=True
    )
