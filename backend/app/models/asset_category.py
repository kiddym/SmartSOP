"""资产分类（每租户）。"""

from __future__ import annotations

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin, UUIDMixin


class AssetCategory(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    __tablename__ = "tb_asset_category"
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_asset_category_company_name"),
    )

    name: Mapped[str] = mapped_column(String(128), nullable=False)
