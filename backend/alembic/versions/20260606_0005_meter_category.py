"""meter category: 新建 tb_meter_category + tb_meter 加 meter_category_id

Revision ID: meter_category
Revises: ui_module_visibility
Create Date: 2026-06-06

手工撰写（MySQL 生产 + SQLite 开发/测试）。
- 新建 tb_meter_category（UUID+Timestamp+SoftDelete+Tenant，唯一 (company_id, name)）；
- tb_meter 用 batch_alter_table 加 meter_category_id 列（可空 FK→tb_meter_category，
  ondelete SET NULL）。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.models.base import DATETIME6

revision: str = "meter_category"
down_revision: str | Sequence[str] | None = "ui_module_visibility"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tb_meter_category",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(length=36),
            sa.ForeignKey("tb_company.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("deleted_at", DATETIME6, nullable=True),
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
        sa.UniqueConstraint("company_id", "name", name="uq_meter_category_company_name"),
    )
    op.create_index(
        "ix_tb_meter_category_company_id", "tb_meter_category", ["company_id"]
    )
    op.create_index(
        "ix_tb_meter_category_is_active", "tb_meter_category", ["is_active"]
    )
    op.create_index(
        "ix_tb_meter_category_created_at", "tb_meter_category", ["created_at"]
    )

    with op.batch_alter_table("tb_meter") as batch_op:
        batch_op.add_column(
            sa.Column("meter_category_id", sa.String(length=36), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_tb_meter_meter_category_id",
            "tb_meter_category",
            ["meter_category_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_tb_meter_meter_category_id", ["meter_category_id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("tb_meter") as batch_op:
        batch_op.drop_index("ix_tb_meter_meter_category_id")
        batch_op.drop_constraint("fk_tb_meter_meter_category_id", type_="foreignkey")
        batch_op.drop_column("meter_category_id")

    # MySQL DROP TABLE 连带删索引与 FK；仅 SQLite 显式删索引（保持既有验证行为）。
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("ix_tb_meter_category_created_at", table_name="tb_meter_category")
        op.drop_index("ix_tb_meter_category_is_active", table_name="tb_meter_category")
        op.drop_index("ix_tb_meter_category_company_id", table_name="tb_meter_category")
    op.drop_table("tb_meter_category")
