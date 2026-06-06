"""Workflow：工单触发的规则引擎（每租户）。

conditions/actions 以 JSON 列存：均为列表，结构由 schema 层校验。
- conditions: [{field, op, value}]，全部满足才匹配（空列表=总匹配）。
- actions: [{type, value}]，匹配后按序应用到工单字段。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class Workflow(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_workflow"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    trigger: Mapped[str] = mapped_column(String(48), nullable=False)
    conditions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    actions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
