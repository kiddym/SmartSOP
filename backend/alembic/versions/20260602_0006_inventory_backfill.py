"""inventory backfill: 6 张关联表 + tb_purchase_order_category + PO 5 列

Revision ID: inventory_backfill
Revises: asset_downtime_propagation (rebased at merge; was workorder_labor_cost)
Create Date: 2026-06-02

手工撰写（MySQL 生产 + SQLite 开发/测试）。本轮库存采购补全统一迁移：
- 新建 6 张多对多关联表：tb_part_location / tb_part_pm / tb_vendor_asset /
  tb_vendor_location / tb_customer_asset / tb_customer_location
  （挂 UUID + Timestamp + Tenant，无 SoftDelete；company_id + 两 FK 列三索引）；
- 新建 tb_purchase_order_category（采购单分类，per-company，含 SoftDelete）；
- tb_purchase_order 加 5 列：category_id（FK→分类，SET NULL，带索引）、
  shipping_address / shipping_method / terms_of_payment（NOT NULL server_default=""）、
  expected_delivery_date（Date nullable）。

升序：先建分类表（PO.category_id FK 指向它），再建 6 关联表，最后 batch 改 PO。
降序逆序：先 batch 去 PO 5 列，再 drop 6 关联表，最后 drop 分类表。

MySQL 全链 alembic 重放受既有 initial_schema 的 TEXT server_default 问题阻塞
（与本迁移无关）；本迁移 DDL 以配套单测（SQLite up/down 可重放）验证，全链待
生产手验。合并 main 时按 backfill-merge-runbook 把 down_revision rebase 到当时
head，保持线性单 head。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.models.base import DATETIME6

revision: str = "inventory_backfill"
down_revision: str | Sequence[str] | None = "asset_downtime_propagation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ts() -> list[sa.Column]:
    """关联表/分类表公共时间戳列（DATETIME6 NOT NULL）。"""
    return [
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
    ]


def _company_fk() -> sa.Column:
    """租户列 company_id（FK→tb_company，CASCADE，NOT NULL）。"""
    return sa.Column(
        "company_id",
        sa.String(length=36),
        sa.ForeignKey("tb_company.id", ondelete="CASCADE"),
        nullable=False,
    )


def _create_join_table(
    table: str,
    left_col: str,
    left_target: str,
    right_col: str,
    right_target: str,
    uq_name: str,
) -> None:
    """建一张多对多关联表 + company_id/左列/右列三索引（与既有关联表风格一致）。"""
    op.create_table(
        table,
        sa.Column("id", sa.String(length=36), primary_key=True),
        _company_fk(),
        sa.Column(
            left_col,
            sa.String(length=36),
            sa.ForeignKey(f"{left_target}.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            right_col,
            sa.String(length=36),
            sa.ForeignKey(f"{right_target}.id", ondelete="CASCADE"),
            nullable=False,
        ),
        *_ts(),
        sa.UniqueConstraint(left_col, right_col, name=uq_name),
    )
    op.create_index(f"ix_{table}_company_id", table, ["company_id"])
    op.create_index(f"ix_{table}_{left_col}", table, [left_col])
    op.create_index(f"ix_{table}_{right_col}", table, [right_col])


def _drop_join_table(table: str, left_col: str, right_col: str) -> None:
    """逆序 drop 关联表：先 drop 三索引再 drop_table。"""
    op.drop_index(f"ix_{table}_{right_col}", table_name=table)
    op.drop_index(f"ix_{table}_{left_col}", table_name=table)
    op.drop_index(f"ix_{table}_company_id", table_name=table)
    op.drop_table(table)


def upgrade() -> None:
    # --- tb_purchase_order_category（先建，PO.category_id FK 指向它） ---
    op.create_table(
        "tb_purchase_order_category",
        sa.Column("id", sa.String(length=36), primary_key=True),
        _company_fk(),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        *_ts(),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", DATETIME6, nullable=True),
        sa.UniqueConstraint(
            "company_id", "name", name="uq_purchase_order_category_company_name"
        ),
    )
    op.create_index(
        "ix_tb_purchase_order_category_company_id",
        "tb_purchase_order_category",
        ["company_id"],
    )
    op.create_index(
        "ix_tb_purchase_order_category_created_at",
        "tb_purchase_order_category",
        ["created_at"],
    )
    op.create_index(
        "ix_tb_purchase_order_category_is_active",
        "tb_purchase_order_category",
        ["is_active"],
    )

    # --- 6 张多对多关联表 ---
    _create_join_table(
        "tb_part_location", "part_id", "tb_part", "location_id", "tb_location",
        "uq_part_location",
    )
    _create_join_table(
        "tb_part_pm", "part_id", "tb_part", "pm_id", "tb_preventive_maintenance",
        "uq_part_pm",
    )
    _create_join_table(
        "tb_vendor_asset", "vendor_id", "tb_vendor", "asset_id", "tb_asset",
        "uq_vendor_asset",
    )
    _create_join_table(
        "tb_vendor_location", "vendor_id", "tb_vendor", "location_id", "tb_location",
        "uq_vendor_location",
    )
    _create_join_table(
        "tb_customer_asset", "customer_id", "tb_customer", "asset_id", "tb_asset",
        "uq_customer_asset",
    )
    _create_join_table(
        "tb_customer_location", "customer_id", "tb_customer", "location_id", "tb_location",
        "uq_customer_location",
    )

    # --- tb_purchase_order 加 5 列（batch_alter_table 走 SQLite 表重建安全） ---
    with op.batch_alter_table("tb_purchase_order") as batch_op:
        # category_id 在列定义里直接带 FK，SQLite 表重建一并生效、MySQL 也成立
        batch_op.add_column(
            sa.Column(
                "category_id",
                sa.String(length=36),
                sa.ForeignKey(
                    "tb_purchase_order_category.id",
                    name="fk_tb_purchase_order_category_id",
                    ondelete="SET NULL",
                ),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "shipping_address", sa.String(length=500), server_default="", nullable=False
            )
        )
        batch_op.add_column(
            sa.Column(
                "shipping_method", sa.String(length=120), server_default="", nullable=False
            )
        )
        batch_op.add_column(
            sa.Column(
                "terms_of_payment", sa.String(length=200), server_default="", nullable=False
            )
        )
        batch_op.add_column(sa.Column("expected_delivery_date", sa.Date(), nullable=True))
    op.create_index(
        "ix_tb_purchase_order_category_id", "tb_purchase_order", ["category_id"]
    )


def downgrade() -> None:
    # --- 先回退 PO 5 列（及索引），逆序 ---
    op.drop_index("ix_tb_purchase_order_category_id", table_name="tb_purchase_order")
    with op.batch_alter_table("tb_purchase_order") as batch_op:
        batch_op.drop_column("expected_delivery_date")
        batch_op.drop_column("terms_of_payment")
        batch_op.drop_column("shipping_method")
        batch_op.drop_column("shipping_address")
        batch_op.drop_column("category_id")

    # --- 再 drop 6 关联表 ---
    _drop_join_table("tb_customer_location", "customer_id", "location_id")
    _drop_join_table("tb_customer_asset", "customer_id", "asset_id")
    _drop_join_table("tb_vendor_location", "vendor_id", "location_id")
    _drop_join_table("tb_vendor_asset", "vendor_id", "asset_id")
    _drop_join_table("tb_part_pm", "part_id", "pm_id")
    _drop_join_table("tb_part_location", "part_id", "location_id")

    # --- 最后 drop 分类表（先 drop 三索引再 drop_table） ---
    op.drop_index(
        "ix_tb_purchase_order_category_is_active", table_name="tb_purchase_order_category"
    )
    op.drop_index(
        "ix_tb_purchase_order_category_created_at", table_name="tb_purchase_order_category"
    )
    op.drop_index(
        "ix_tb_purchase_order_category_company_id", table_name="tb_purchase_order_category"
    )
    op.drop_table("tb_purchase_order_category")
