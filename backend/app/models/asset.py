"""图片资源与引用模型（data-model §3.10 / §3.11）。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, BigInteger, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    DATETIME6,
    Base,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    UUIDMixin,
    utcnow,
)

if TYPE_CHECKING:
    pass


class ProcedureAsset(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    """图片二进制资源（本公司内 sha256 去重）。Word 导入抽图入库（§25.2）。"""

    __tablename__ = "tb_procedure_asset"
    __table_args__ = (
        UniqueConstraint("company_id", "sha256", name="uq_tb_procedure_asset_company_sha256"),
    )

    sha256: Mapped[str] = mapped_column(String(64))
    storage_path: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    width: Mapped[int | None] = mapped_column(Integer, default=None)
    height: Mapped[int | None] = mapped_column(Integer, default=None)
    source_meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    references: Mapped[list[ProcedureAssetReference]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )


class ProcedureAssetReference(Base, UUIDMixin, TenantMixin):
    """资源引用关联表（asset_id, procedure_id）。仅追加 created_at（§3.11）。"""

    __tablename__ = "tb_procedure_asset_reference"

    asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_procedure_asset.id", ondelete="RESTRICT")
    )
    procedure_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_procedure.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DATETIME6, default=utcnow)

    asset: Mapped[ProcedureAsset] = relationship(back_populates="references")

    __table_args__ = (
        Index(
            "uq_tb_procedure_asset_reference_company_asset_procedure",
            "company_id",
            "asset_id",
            "procedure_id",
            unique=True,
        ),
        Index("ix_tb_procedure_asset_reference_procedure_id", "procedure_id"),
        Index("ix_tb_procedure_asset_reference_asset_id", "asset_id"),
    )
