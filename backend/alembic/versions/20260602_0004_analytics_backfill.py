"""analytics backfill: tb_work_order_category + tb_work_order.(category_id, created_by_user_id)

Revision ID: analytics_backfill
Revises: workorder_labor_cost
Create Date: 2026-06-02

Hand-authored (MySQL prod + SQLite dev/test)。新建工单分类表并给工单加两列：
- tb_work_order_category（工单分类，per-company，镜像 tb_time_category）；
- tb_work_order.category_id（FK→分类，删分类时置空 SET NULL，建索引）；
- tb_work_order.created_by_user_id（创建者，仅记录无 FK，建索引）。

全新表/列、无数据平移。MySQL 全链 alembic 重放受既有 initial_schema 的
TEXT server_default 问题阻塞（与本迁移无关）；本迁移 DDL 以最小 fixture 单测
在 SQLite 上重放 up/down 验证，全链待生产手验。

SQLite ALTER 不支持 create_foreign_key/drop_constraint(foreignkey)，故对
tb_work_order 两列的加列/索引/FK 用 batch_alter_table 包裹（SQLite 安全，
MySQL 退化为直接 ALTER）。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.models.base import DATETIME6

revision: str = "analytics_backfill"
down_revision: str | Sequence[str] | None = "workorder_labor_cost"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- tb_work_order_category ---
    op.create_table(
        "tb_work_order_category",
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", DATETIME6, nullable=True),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["tb_company.id"],
            name=op.f("fk_tb_work_order_category_company_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tb_work_order_category")),
        sa.UniqueConstraint(
            "company_id", "name", name="uq_work_order_category_company_name"
        ),
    )
    op.create_index(
        op.f("ix_tb_work_order_category_company_id"),
        "tb_work_order_category",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tb_work_order_category_created_at"),
        "tb_work_order_category",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tb_work_order_category_is_active"),
        "tb_work_order_category",
        ["is_active"],
        unique=False,
    )

    # --- tb_work_order 两列（batch 包裹，兼容 SQLite ALTER 限制）---
    with op.batch_alter_table("tb_work_order") as batch:
        batch.add_column(sa.Column("category_id", sa.String(length=36), nullable=True))
        batch.add_column(
            sa.Column("created_by_user_id", sa.String(length=36), nullable=True)
        )
        batch.create_index(
            op.f("ix_tb_work_order_category_id"), ["category_id"], unique=False
        )
        batch.create_index(
            op.f("ix_tb_work_order_created_by_user_id"),
            ["created_by_user_id"],
            unique=False,
        )
        batch.create_foreign_key(
            op.f("fk_tb_work_order_category_id"),
            "tb_work_order_category",
            ["category_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("tb_work_order") as batch:
        batch.drop_constraint(
            op.f("fk_tb_work_order_category_id"), type_="foreignkey"
        )
        batch.drop_index(op.f("ix_tb_work_order_created_by_user_id"))
        batch.drop_index(op.f("ix_tb_work_order_category_id"))
        batch.drop_column("created_by_user_id")
        batch.drop_column("category_id")

    op.drop_index(
        op.f("ix_tb_work_order_category_is_active"),
        table_name="tb_work_order_category",
    )
    op.drop_index(
        op.f("ix_tb_work_order_category_created_at"),
        table_name="tb_work_order_category",
    )
    op.drop_index(
        op.f("ix_tb_work_order_category_company_id"),
        table_name="tb_work_order_category",
    )
    op.drop_table("tb_work_order_category")
