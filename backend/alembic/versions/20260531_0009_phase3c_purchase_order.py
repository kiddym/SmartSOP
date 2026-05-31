"""phase3c purchase order: purchase_order + line + activity

Revision ID: phase3c_purchase_order
Revises: phase3b_vendor
Create Date: 2026-05-31

Hand-authored (MySQL prod + SQLite dev/test). New tables -> create_table.
Works on both dialects, no branching.
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import DATETIME6

revision: str = "phase3c_purchase_order"
down_revision: str | Sequence[str] | None = "phase3b_vendor"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ts() -> list[sa.Column]:
    return [
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
    ]


def _soft() -> list[sa.Column]:
    return [
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", DATETIME6, nullable=True),
    ]


def _company_fk() -> sa.Column:
    return sa.Column(
        "company_id", sa.String(36),
        sa.ForeignKey("tb_company.id", ondelete="CASCADE"), nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "tb_purchase_order",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("custom_id", sa.String(20), nullable=False),
        sa.Column("vendor_id", sa.String(36),
                  sa.ForeignKey("tb_vendor.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.Enum(
            "DRAFT", "SUBMITTED", "APPROVED", "REJECTED", "CANCELED",
            name="purchaseorderstatus"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("resolution_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("resolved_by_user_id", sa.String(36), nullable=True),
        sa.Column("resolved_at", DATETIME6, nullable=True),
        *_ts(), *_soft(),
    )
    op.create_index("ix_tb_purchase_order_company_id", "tb_purchase_order", ["company_id"])
    op.create_index("ix_tb_purchase_order_vendor_id", "tb_purchase_order", ["vendor_id"])

    op.create_table(
        "tb_purchase_order_line",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("purchase_order_id", sa.String(36),
                  sa.ForeignKey("tb_purchase_order.id", ondelete="CASCADE"), nullable=False),
        sa.Column("part_id", sa.String(36),
                  sa.ForeignKey("tb_part.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=False, server_default="0"),
        *_ts(),
    )
    op.create_index("ix_tb_purchase_order_line_company_id", "tb_purchase_order_line", ["company_id"])
    op.create_index("ix_tb_purchase_order_line_purchase_order_id", "tb_purchase_order_line", ["purchase_order_id"])
    op.create_index("ix_tb_purchase_order_line_part_id", "tb_purchase_order_line", ["part_id"])

    op.create_table(
        "tb_purchase_order_activity",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("purchase_order_id", sa.String(36),
                  sa.ForeignKey("tb_purchase_order.id", ondelete="CASCADE"), nullable=False),
        sa.Column("activity_type", sa.String(40), nullable=False),
        sa.Column("actor_user_id", sa.String(36), nullable=True),
        sa.Column("from_status", sa.String(40), nullable=True),
        sa.Column("to_status", sa.String(40), nullable=True),
        sa.Column("comment", sa.Text(), nullable=False, server_default=""),
        *_ts(),
    )
    op.create_index("ix_tb_purchase_order_activity_company_id", "tb_purchase_order_activity", ["company_id"])
    op.create_index("ix_tb_purchase_order_activity_purchase_order_id", "tb_purchase_order_activity", ["purchase_order_id"])


def downgrade() -> None:
    op.drop_index("ix_tb_purchase_order_activity_purchase_order_id", table_name="tb_purchase_order_activity")
    op.drop_index("ix_tb_purchase_order_activity_company_id", table_name="tb_purchase_order_activity")
    op.drop_table("tb_purchase_order_activity")
    op.drop_index("ix_tb_purchase_order_line_part_id", table_name="tb_purchase_order_line")
    op.drop_index("ix_tb_purchase_order_line_purchase_order_id", table_name="tb_purchase_order_line")
    op.drop_index("ix_tb_purchase_order_line_company_id", table_name="tb_purchase_order_line")
    op.drop_table("tb_purchase_order_line")
    op.drop_index("ix_tb_purchase_order_vendor_id", table_name="tb_purchase_order")
    op.drop_index("ix_tb_purchase_order_company_id", table_name="tb_purchase_order")
    op.drop_table("tb_purchase_order")
