"""phase3b vendor: vendor + customer + cost_category + vendor_part + customer_part

Revision ID: phase3b_vendor
Revises: phase3a_part
Create Date: 2026-05-31

Hand-authored (MySQL prod + SQLite dev/test). New tables -> create_table.
Works on both dialects, no branching.
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import DATETIME6

revision: str = "phase3b_vendor"
down_revision: str | Sequence[str] | None = "phase3a_part"
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
        "tb_vendor",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("vendor_type", sa.String(120), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False, server_default=sa.text("('')")),
        sa.Column("rate", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("address", sa.String(500), nullable=False, server_default=""),
        sa.Column("phone", sa.String(60), nullable=False, server_default=""),
        sa.Column("email", sa.String(200), nullable=False, server_default=""),
        sa.Column("website", sa.String(300), nullable=False, server_default=""),
        *_ts(), *_soft(),
    )
    op.create_index("ix_tb_vendor_company_id", "tb_vendor", ["company_id"])

    op.create_table(
        "tb_customer",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("customer_type", sa.String(120), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False, server_default=sa.text("('')")),
        sa.Column("rate", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("billing_currency", sa.String(8), nullable=False, server_default=""),
        sa.Column("address", sa.String(500), nullable=False, server_default=""),
        sa.Column("phone", sa.String(60), nullable=False, server_default=""),
        sa.Column("email", sa.String(200), nullable=False, server_default=""),
        sa.Column("website", sa.String(300), nullable=False, server_default=""),
        *_ts(), *_soft(),
    )
    op.create_index("ix_tb_customer_company_id", "tb_customer", ["company_id"])

    op.create_table(
        "tb_cost_category",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=sa.text("('')")),
        *_ts(), *_soft(),
        sa.UniqueConstraint("company_id", "name", name="uq_cost_category_company_name"),
    )
    op.create_index("ix_tb_cost_category_company_id", "tb_cost_category", ["company_id"])

    op.create_table(
        "tb_vendor_part",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("vendor_id", sa.String(36),
                  sa.ForeignKey("tb_vendor.id", ondelete="CASCADE"), nullable=False),
        sa.Column("part_id", sa.String(36),
                  sa.ForeignKey("tb_part.id", ondelete="CASCADE"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("vendor_id", "part_id", name="uq_vendor_part"),
    )
    op.create_index("ix_tb_vendor_part_company_id", "tb_vendor_part", ["company_id"])
    op.create_index("ix_tb_vendor_part_vendor_id", "tb_vendor_part", ["vendor_id"])
    op.create_index("ix_tb_vendor_part_part_id", "tb_vendor_part", ["part_id"])

    op.create_table(
        "tb_customer_part",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("customer_id", sa.String(36),
                  sa.ForeignKey("tb_customer.id", ondelete="CASCADE"), nullable=False),
        sa.Column("part_id", sa.String(36),
                  sa.ForeignKey("tb_part.id", ondelete="CASCADE"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("customer_id", "part_id", name="uq_customer_part"),
    )
    op.create_index("ix_tb_customer_part_company_id", "tb_customer_part", ["company_id"])
    op.create_index("ix_tb_customer_part_customer_id", "tb_customer_part", ["customer_id"])
    op.create_index("ix_tb_customer_part_part_id", "tb_customer_part", ["part_id"])


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("ix_tb_customer_part_part_id", table_name="tb_customer_part")
        op.drop_index("ix_tb_customer_part_customer_id", table_name="tb_customer_part")
        op.drop_index("ix_tb_customer_part_company_id", table_name="tb_customer_part")
    op.drop_table("tb_customer_part")
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("ix_tb_vendor_part_part_id", table_name="tb_vendor_part")
        op.drop_index("ix_tb_vendor_part_vendor_id", table_name="tb_vendor_part")
        op.drop_index("ix_tb_vendor_part_company_id", table_name="tb_vendor_part")
    op.drop_table("tb_vendor_part")
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("ix_tb_cost_category_company_id", table_name="tb_cost_category")
    op.drop_table("tb_cost_category")
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("ix_tb_customer_company_id", table_name="tb_customer")
    op.drop_table("tb_customer")
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("ix_tb_vendor_company_id", table_name="tb_vendor")
    op.drop_table("tb_vendor")
