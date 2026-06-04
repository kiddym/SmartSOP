"""work order 2B backfill: WorkOrder 加 8 列 + tb_work_order_relation

Revision ID: workorder_2b_backfill
Revises: inventory_backfill
Create Date: 2026-06-04

手工撰写（MySQL 生产 + SQLite 开发/测试）。
- tb_work_order 加 8 列（batch_alter_table，SQLite 表重建安全）：
  completed_by_user_id / feedback / urgent / estimated_duration /
  estimated_start_date / first_responded_at / archived / is_compliant；
- 新建 tb_work_order_relation（UUID+Timestamp+Tenant，单有向记录）。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.models.base import DATETIME6

revision: str = "workorder_2b_backfill"
down_revision: str | Sequence[str] | None = "inventory_backfill"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tb_work_order") as batch_op:
        batch_op.add_column(sa.Column("completed_by_user_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("feedback", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("urgent", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch_op.add_column(sa.Column("estimated_duration", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("estimated_start_date", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("first_responded_at", DATETIME6, nullable=True))
        batch_op.add_column(
            sa.Column("archived", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch_op.add_column(sa.Column("is_compliant", sa.Boolean(), nullable=True))

    op.create_table(
        "tb_work_order_relation",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(length=36),
            sa.ForeignKey("tb_company.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_work_order_id",
            sa.String(length=36),
            sa.ForeignKey("tb_work_order.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_work_order_id",
            sa.String(length=36),
            sa.ForeignKey("tb_work_order.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "relation_type",
            sa.Enum("DUPLICATE", "RELATED", "SPLIT", "BLOCKS", name="workorderrelationtype"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
        sa.UniqueConstraint(
            "source_work_order_id",
            "target_work_order_id",
            "relation_type",
            name="uq_work_order_relation",
        ),
    )
    op.create_index(
        "ix_tb_work_order_relation_company_id", "tb_work_order_relation", ["company_id"]
    )
    op.create_index(
        "ix_tb_work_order_relation_created_at", "tb_work_order_relation", ["created_at"]
    )
    op.create_index(
        "ix_tb_work_order_relation_source_work_order_id",
        "tb_work_order_relation",
        ["source_work_order_id"],
    )
    op.create_index(
        "ix_tb_work_order_relation_target_work_order_id",
        "tb_work_order_relation",
        ["target_work_order_id"],
    )


def downgrade() -> None:
    # MySQL 拒绝先删被 FK 占用的索引（1553）；DROP TABLE 连带删索引与 FK，故仅 SQLite
    # 显式删索引（保持其既有验证行为），MySQL 直接 DROP TABLE。
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index(
            "ix_tb_work_order_relation_target_work_order_id",
            table_name="tb_work_order_relation",
        )
        op.drop_index(
            "ix_tb_work_order_relation_source_work_order_id",
            table_name="tb_work_order_relation",
        )
        op.drop_index(
            "ix_tb_work_order_relation_created_at", table_name="tb_work_order_relation"
        )
        op.drop_index(
            "ix_tb_work_order_relation_company_id", table_name="tb_work_order_relation"
        )
    op.drop_table("tb_work_order_relation")

    with op.batch_alter_table("tb_work_order") as batch_op:
        batch_op.drop_column("is_compliant")
        batch_op.drop_column("archived")
        batch_op.drop_column("first_responded_at")
        batch_op.drop_column("estimated_start_date")
        batch_op.drop_column("estimated_duration")
        batch_op.drop_column("urgent")
        batch_op.drop_column("feedback")
        batch_op.drop_column("completed_by_user_id")
