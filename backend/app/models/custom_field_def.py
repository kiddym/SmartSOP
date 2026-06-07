"""业务实体动态自定义字段定义（多态 entity_type）。与 SOP ProcedureField 解耦。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    UUIDMixin,
)


class CustomFieldDef(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    """业务实体自定义字段定义。entity_type 多态；key 创建后不可改，按 (company, entity_type) 唯一。"""

    __tablename__ = "tb_custom_field_def"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "entity_type", "key", name="uq_custom_field_def_company_entity_key"
        ),
    )

    # work_order / asset / request / location / part
    entity_type: Mapped[str] = mapped_column(String(32), index=True)
    key: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100))
    # text / number / date / select / multi_select / checkbox / textarea
    field_type: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(Text, default="", server_default=text("('')"))
    required: Mapped[bool] = mapped_column(default=False, server_default="0")
    default_value: Mapped[Any | None] = mapped_column(JSON, default=None, nullable=True)
    options: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    validation_rules: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # active / archived
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active")
