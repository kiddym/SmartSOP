"""表单字段配置：每 company × 表单 × 字段 一行，控制显隐/必填。

服务请求表单（REQUEST）与工单表单（WORK_ORDER）的字段可见性与必填配置。
取代 Atlas FieldConfiguration（挂在 WorkOrderConfiguration /
WorkOrderRequestConfiguration 下）的功能，净室独立实现。
"""

from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class FormFieldConfig(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_form_field_config"
    __table_args__ = (
        UniqueConstraint("company_id", "form_key", "field_name", name="uq_form_field_config"),
    )

    form_key: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(64), nullable=False)
    visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
