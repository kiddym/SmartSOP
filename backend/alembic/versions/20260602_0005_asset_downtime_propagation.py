"""asset downtime propagation: tb_asset_downtime + source_asset_id + prior_status

Revision ID: asset_downtime_propagation
Revises: analytics_backfill (rebased at merge; was workorder_labor_cost)
Create Date: 2026-06-02

Hand-authored (MySQL prod + SQLite dev/test)。给 tb_asset_downtime 加级联溯源两列。
全新列、无数据平移。

合并协调：本迁移与分析补全 analytics_backfill 都以 workorder_labor_cost 为 down_revision
（各自分支）。两分支合入 main 时，后合入者须把本 down_revision 改指向先合入者的 revision，
形成单一线性链（迁移单测只验 DDL，不依赖链顺序）。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "asset_downtime_propagation"
down_revision: str | Sequence[str] | None = "analytics_backfill"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tb_asset_downtime") as batch:
        batch.add_column(sa.Column("source_asset_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("prior_status", sa.String(length=20), nullable=True))
        batch.create_index(
            batch.f("ix_tb_asset_downtime_source_asset_id"), ["source_asset_id"], unique=False
        )
        batch.create_foreign_key(
            batch.f("fk_tb_asset_downtime_source_asset_id"),
            "tb_asset",
            ["source_asset_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("tb_asset_downtime") as batch:
        batch.drop_constraint(
            batch.f("fk_tb_asset_downtime_source_asset_id"), type_="foreignkey"
        )
        batch.drop_index(batch.f("ix_tb_asset_downtime_source_asset_id"))
        batch.drop_column("prior_status")
        batch.drop_column("source_asset_id")
