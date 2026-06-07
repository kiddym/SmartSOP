"""位置（自引用树）及其负责人/团队关联（每租户）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Float, ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin, UUIDMixin


class Location(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_location"

    custom_id: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default=text("('')"))
    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_location.id", ondelete="RESTRICT"), index=True
    )
    address: Mapped[str] = mapped_column(String(500), default="", server_default="")
    longitude: Mapped[float | None] = mapped_column(Float, default=None)
    latitude: Mapped[float | None] = mapped_column(Float, default=None)
    image_url: Mapped[str | None] = mapped_column(String(512), default=None)
    # 业务自定义字段值（按 CustomFieldDef.key 存；JSON 括号表达式默认避开 MySQL 1101）
    custom_values: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default=text("('{}')")
    )


class LocationUser(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_location_user"
    __table_args__ = (UniqueConstraint("location_id", "user_id", name="uq_location_user"),)

    location_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_location.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_user.id", ondelete="CASCADE"), index=True
    )


class LocationTeam(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_location_team"
    __table_args__ = (UniqueConstraint("location_id", "team_id", name="uq_location_team"),)

    location_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_location.id", ondelete="CASCADE"), index=True
    )
    team_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_team.id", ondelete="CASCADE"), index=True
    )
