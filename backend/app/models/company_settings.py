"""公司级配置（每 company 一行 singleton）。"""

from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class CompanySettings(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "tb_company_settings"
    # singleton：每 company 至多一行（DB 级硬化，配合 service.get_or_create）
    __table_args__ = (UniqueConstraint("company_id", name="uq_company_settings_company"),)

    date_format: Mapped[str] = mapped_column(
        String(32), default="YYYY-MM-DD", server_default="YYYY-MM-DD"
    )
    timezone: Mapped[str] = mapped_column(
        String(64), default="Asia/Shanghai", server_default="Asia/Shanghai"
    )
    default_currency_code: Mapped[str] = mapped_column(
        String(8), default="CNY", server_default="CNY"
    )
    auto_assign: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    # General preferences (公司级业务开关).
    language: Mapped[str] = mapped_column(String(16), default="zh-CN", server_default="zh-CN")
    business_type: Mapped[str | None] = mapped_column(String(64), default=None)
    wo_update_for_requesters: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0"
    )
    disable_closed_wo_notification: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0"
    )
    ask_feedback_on_wo_closed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0"
    )
    labor_cost_in_total_cost: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="1"
    )
    simplified_work_order: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    # PM 到期前 N 天发提醒（0=不提醒），供 E6 排程提醒使用。
    days_before_pm_notification: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    auto_assign_requests: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    # 导航模块显隐（UiConfiguration）：默认全显。
    show_requests: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    show_locations: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    show_meters: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    show_vendors_customers: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="1"
    )
