"""自定义字段定义模型（全局，data-model §3.7）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    NullableTenantMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDMixin,
)


class ProcedureField(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, NullableTenantMixin):
    """全局自定义字段定义。key 创建后不可改（Q254）。"""

    __tablename__ = "tb_procedure_field"

    name: Mapped[str] = mapped_column(String(100))
    # 编程键：英文小写/数字/下划线，全局唯一，创建后不可改（Q254）
    key: Mapped[str] = mapped_column(String(100), unique=True)
    # text / number / date / select / multi_select / checkbox / textarea
    field_type: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    required: Mapped[bool] = mapped_column(default=False, server_default="0")
    default_value: Mapped[Any | None] = mapped_column(JSON, default=None, nullable=True)
    options: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    # 标准 JSON Schema（Q-C6）
    validation_rules: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    show_on_cover: Mapped[bool] = mapped_column(default=False, server_default="0")
    # active / archived（archived 后已填值保留只读，Q255）
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active")
