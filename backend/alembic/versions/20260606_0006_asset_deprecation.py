"""asset deprecation: 新建 tb_asset_deprecation（资产 1:1 折旧信息）

Revision ID: asset_deprecation
Revises: meter_category
Create Date: 2026-06-06

手工撰写（MySQL 生产 + SQLite 开发/测试）。
- 新建 tb_asset_deprecation（UUID+Timestamp+Tenant）；
- asset_id 唯一 FK→tb_asset（ondelete CASCADE，随资产删除）；
- company_id FK→tb_company（ondelete CASCADE）+ 索引；
- 折旧原始参数列均可空，当前价值在应用层计算（不落库）。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.models.base import DATETIME6

revision: str = "asset_deprecation"
down_revision: str | Sequence[str] | None = "meter_category"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tb_asset_deprecation",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(length=36),
            sa.ForeignKey("tb_company.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "asset_id",
            sa.String(length=36),
            sa.ForeignKey("tb_asset.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("purchase_price", sa.Numeric(18, 2), nullable=True),
        sa.Column("purchase_date", sa.Date(), nullable=True),
        sa.Column("residual_value", sa.Numeric(18, 2), nullable=True),
        sa.Column("useful_life_years", sa.Integer(), nullable=True),
        sa.Column("rate", sa.Numeric(9, 4), nullable=True),
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
        sa.UniqueConstraint("asset_id", name="uq_asset_deprecation_asset_id"),
    )
    op.create_index(
        "ix_tb_asset_deprecation_company_id", "tb_asset_deprecation", ["company_id"]
    )
    op.create_index(
        "ix_tb_asset_deprecation_asset_id", "tb_asset_deprecation", ["asset_id"]
    )
    op.create_index(
        "ix_tb_asset_deprecation_created_at", "tb_asset_deprecation", ["created_at"]
    )


def downgrade() -> None:
    # MySQL DROP TABLE 连带删索引与 FK；仅 SQLite 显式删索引（保持既有验证行为）。
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index(
            "ix_tb_asset_deprecation_created_at", table_name="tb_asset_deprecation"
        )
        op.drop_index(
            "ix_tb_asset_deprecation_asset_id", table_name="tb_asset_deprecation"
        )
        op.drop_index(
            "ix_tb_asset_deprecation_company_id", table_name="tb_asset_deprecation"
        )
    op.drop_table("tb_asset_deprecation")
