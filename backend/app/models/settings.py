"""全局设置模型（单例，data-model §3.8）。"""

from __future__ import annotations

from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class ProcedureSettings(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """全局设置（单例）。seed 时创建唯一一条。"""

    __tablename__ = "tb_procedure_settings"

    # 本期恒 true、UI 不暴露（Q232）
    enable_version_control: Mapped[bool] = mapped_column(default=True, server_default="1")
    # 审批开关（Q242，受控反转 B3）；ON 时 publish 前调 stub 闸门
    enable_approval_workflow: Mapped[bool] = mapped_column(default=False, server_default="0")
    max_version_number: Mapped[int] = mapped_column(Integer, default=100, server_default="100")
    # 0=不自动归档；0.1.0 不接线、设置页隐藏（Q259/Q337）
    auto_archive_days: Mapped[int] = mapped_column(Integer, default=365, server_default="365")
    require_read_confirmation: Mapped[bool] = mapped_column(default=False, server_default="0")
    default_risk_level: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    default_quality_level: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    # 乐观锁版本号（Q18 / data-model §4.6）
    revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
