"""workorder labor cost: tb_time_category + tb_work_order_labor + tb_work_order_additional_cost

Revision ID: workorder_labor_cost
Revises: universal_attachment
Create Date: 2026-06-02

Hand-authored (MySQL prod + SQLite dev/test). 新建工单工时成本三表：
- tb_time_category（工时分类，per-company，默认小时费率）;
- tb_work_order_labor（工时，计时器+手填，费率快照）;
- tb_work_order_additional_cost（额外成本，复用 tb_cost_category）。

全新表、无数据平移。MySQL 全链 alembic 重放受既有 initial_schema 的 TEXT
server_default 问题阻塞（与本迁移无关）；本迁移 DDL 待按实际版本以最小 fixture 手验。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.models.base import DATETIME6

revision: str = "workorder_labor_cost"
down_revision: str | Sequence[str] | None = "universal_attachment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- tb_time_category ---
    op.create_table(
        "tb_time_category",
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("hourly_rate", sa.Numeric(18, 4), server_default="0", nullable=False),
        sa.Column("description", sa.Text(), server_default=sa.text("('')"), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", DATETIME6, nullable=True),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["tb_company.id"],
            name=op.f("fk_tb_time_category_company_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tb_time_category")),
        sa.UniqueConstraint("company_id", "name", name="uq_time_category_company_name"),
    )
    op.create_index(
        op.f("ix_tb_time_category_company_id"), "tb_time_category", ["company_id"], unique=False
    )
    op.create_index(
        op.f("ix_tb_time_category_created_at"), "tb_time_category", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_tb_time_category_is_active"), "tb_time_category", ["is_active"], unique=False
    )

    # --- tb_work_order_labor ---
    op.create_table(
        "tb_work_order_labor",
        sa.Column("work_order_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("time_category_id", sa.String(length=36), nullable=True),
        sa.Column("started_at", DATETIME6, nullable=True),
        sa.Column("stopped_at", DATETIME6, nullable=True),
        sa.Column("duration_seconds", sa.Integer(), server_default="0", nullable=False),
        sa.Column("hourly_rate", sa.Numeric(18, 4), nullable=False),
        sa.Column("notes", sa.Text(), server_default=sa.text("('')"), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["work_order_id"],
            ["tb_work_order.id"],
            name=op.f("fk_tb_work_order_labor_work_order_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["tb_user.id"],
            name=op.f("fk_tb_work_order_labor_user_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["time_category_id"],
            ["tb_time_category.id"],
            name=op.f("fk_tb_work_order_labor_time_category_id"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["tb_company.id"],
            name=op.f("fk_tb_work_order_labor_company_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tb_work_order_labor")),
    )
    op.create_index(
        op.f("ix_tb_work_order_labor_company_id"),
        "tb_work_order_labor",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tb_work_order_labor_created_at"),
        "tb_work_order_labor",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tb_work_order_labor_user_id"),
        "tb_work_order_labor",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tb_work_order_labor_work_order_id"),
        "tb_work_order_labor",
        ["work_order_id"],
        unique=False,
    )

    # --- tb_work_order_additional_cost ---
    op.create_table(
        "tb_work_order_additional_cost",
        sa.Column("work_order_id", sa.String(length=36), nullable=False),
        sa.Column("cost_category_id", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("description", sa.Text(), server_default=sa.text("('')"), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["work_order_id"],
            ["tb_work_order.id"],
            name=op.f("fk_tb_work_order_additional_cost_work_order_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["cost_category_id"],
            ["tb_cost_category.id"],
            name=op.f("fk_tb_work_order_additional_cost_cost_category_id"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["tb_company.id"],
            name=op.f("fk_tb_work_order_additional_cost_company_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tb_work_order_additional_cost")),
    )
    op.create_index(
        op.f("ix_tb_work_order_additional_cost_company_id"),
        "tb_work_order_additional_cost",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tb_work_order_additional_cost_created_at"),
        "tb_work_order_additional_cost",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tb_work_order_additional_cost_work_order_id"),
        "tb_work_order_additional_cost",
        ["work_order_id"],
        unique=False,
    )


def downgrade() -> None:
    # MySQL：work_order_id/company_id 等列索引被 FK 占用（1553），DROP TABLE 连带清理，
    # 故仅 SQLite 显式删索引（保持其既有验证行为）。
    is_sqlite = op.get_bind().dialect.name == "sqlite"
    if is_sqlite:
        op.drop_index(
            op.f("ix_tb_work_order_additional_cost_work_order_id"),
            table_name="tb_work_order_additional_cost",
        )
        op.drop_index(
            op.f("ix_tb_work_order_additional_cost_created_at"),
            table_name="tb_work_order_additional_cost",
        )
        op.drop_index(
            op.f("ix_tb_work_order_additional_cost_company_id"),
            table_name="tb_work_order_additional_cost",
        )
    op.drop_table("tb_work_order_additional_cost")

    if is_sqlite:
        op.drop_index(
            op.f("ix_tb_work_order_labor_work_order_id"), table_name="tb_work_order_labor"
        )
        op.drop_index(
            op.f("ix_tb_work_order_labor_user_id"), table_name="tb_work_order_labor"
        )
        op.drop_index(
            op.f("ix_tb_work_order_labor_created_at"), table_name="tb_work_order_labor"
        )
        op.drop_index(
            op.f("ix_tb_work_order_labor_company_id"), table_name="tb_work_order_labor"
        )
    op.drop_table("tb_work_order_labor")

    if is_sqlite:
        op.drop_index(
            op.f("ix_tb_time_category_is_active"), table_name="tb_time_category"
        )
        op.drop_index(
            op.f("ix_tb_time_category_created_at"), table_name="tb_time_category"
        )
        op.drop_index(
            op.f("ix_tb_time_category_company_id"), table_name="tb_time_category"
        )
    op.drop_table("tb_time_category")
