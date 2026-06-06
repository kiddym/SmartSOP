"""floor plan: 新建 tb_floor_plan（位置 1:N 平面图）

Revision ID: floor_plan
Revises: asset_deprecation
Create Date: 2026-06-06

手工撰写（MySQL 生产 + SQLite 开发/测试）。
- 新建 tb_floor_plan（UUID+Timestamp+Tenant）；
- location_id FK→tb_location（ondelete CASCADE，随位置删除）+ 索引；
- company_id FK→tb_company（ondelete CASCADE）+ 索引；
- name 必填；image_url / area 可空。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.models.base import DATETIME6

revision: str = "floor_plan"
down_revision: str | Sequence[str] | None = "asset_deprecation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tb_floor_plan",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(length=36),
            sa.ForeignKey("tb_company.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "location_id",
            sa.String(length=36),
            sa.ForeignKey("tb_location.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("image_url", sa.String(length=512), nullable=True),
        sa.Column("area", sa.Numeric(12, 2), nullable=True),
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
    )
    op.create_index("ix_tb_floor_plan_company_id", "tb_floor_plan", ["company_id"])
    op.create_index("ix_tb_floor_plan_location_id", "tb_floor_plan", ["location_id"])
    op.create_index("ix_tb_floor_plan_created_at", "tb_floor_plan", ["created_at"])


def downgrade() -> None:
    # MySQL DROP TABLE 连带删索引与 FK；仅 SQLite 显式删索引（保持既有验证行为）。
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("ix_tb_floor_plan_created_at", table_name="tb_floor_plan")
        op.drop_index("ix_tb_floor_plan_location_id", table_name="tb_floor_plan")
        op.drop_index("ix_tb_floor_plan_company_id", table_name="tb_floor_plan")
    op.drop_table("tb_floor_plan")
