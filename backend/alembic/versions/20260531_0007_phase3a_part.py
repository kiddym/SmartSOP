"""phase3a part: part + part_category + part_consumption + multi_part(+item) + part assoc tables

Revision ID: phase3a_part
Revises: phase2c_meter
Create Date: 2026-05-31

Hand-authored (MySQL prod + SQLite dev/test). New tables -> create_table.
Works on both dialects, no branching.
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import DATETIME6

revision: str = "phase3a_part"
down_revision: str | Sequence[str] | None = "phase2c_meter"
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
        "tb_part_category",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=sa.text("('')")),
        *_ts(), *_soft(),
        sa.UniqueConstraint("company_id", "name", name="uq_part_category_company_name"),
    )
    op.create_index("ix_tb_part_category_company_id", "tb_part_category", ["company_id"])

    op.create_table(
        "tb_part",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("custom_id", sa.String(20), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=sa.text("('')")),
        sa.Column("cost", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("min_quantity", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("unit", sa.String(50), nullable=False, server_default=""),
        sa.Column("barcode", sa.String(120), nullable=True),
        sa.Column("non_stock", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("category_id", sa.String(36),
                  sa.ForeignKey("tb_part_category.id", ondelete="SET NULL"), nullable=True),
        *_ts(), *_soft(),
    )
    op.create_index("ix_tb_part_company_id", "tb_part", ["company_id"])
    op.create_index("ix_tb_part_category_id", "tb_part", ["category_id"])

    op.create_table(
        "tb_part_consumption",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("part_id", sa.String(36),
                  sa.ForeignKey("tb_part.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("work_order_id", sa.String(36),
                  sa.ForeignKey("tb_work_order.id", ondelete="CASCADE"), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=False),
        sa.Column("consumed_by_user_id", sa.String(36), nullable=True),
        sa.Column("consumed_at", DATETIME6, nullable=False),
        *_ts(),
    )
    op.create_index("ix_tb_part_consumption_company_id", "tb_part_consumption", ["company_id"])
    op.create_index("ix_tb_part_consumption_part_id", "tb_part_consumption", ["part_id"])
    op.create_index("ix_tb_part_consumption_work_order_id", "tb_part_consumption", ["work_order_id"])

    op.create_table(
        "tb_multi_part",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("custom_id", sa.String(20), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=sa.text("('')")),
        *_ts(), *_soft(),
    )
    op.create_index("ix_tb_multi_part_company_id", "tb_multi_part", ["company_id"])

    op.create_table(
        "tb_multi_part_item",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("multi_part_id", sa.String(36),
                  sa.ForeignKey("tb_multi_part.id", ondelete="CASCADE"), nullable=False),
        sa.Column("part_id", sa.String(36),
                  sa.ForeignKey("tb_part.id", ondelete="CASCADE"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("multi_part_id", "part_id", name="uq_multi_part_item"),
    )
    op.create_index("ix_tb_multi_part_item_company_id", "tb_multi_part_item", ["company_id"])
    op.create_index("ix_tb_multi_part_item_multi_part_id", "tb_multi_part_item", ["multi_part_id"])
    op.create_index("ix_tb_multi_part_item_part_id", "tb_multi_part_item", ["part_id"])

    op.create_table(
        "tb_part_assignee",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("part_id", sa.String(36),
                  sa.ForeignKey("tb_part.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36),
                  sa.ForeignKey("tb_user.id", ondelete="CASCADE"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("part_id", "user_id", name="uq_part_assignee"),
    )
    op.create_index("ix_tb_part_assignee_company_id", "tb_part_assignee", ["company_id"])
    op.create_index("ix_tb_part_assignee_part_id", "tb_part_assignee", ["part_id"])
    op.create_index("ix_tb_part_assignee_user_id", "tb_part_assignee", ["user_id"])

    op.create_table(
        "tb_part_team",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("part_id", sa.String(36),
                  sa.ForeignKey("tb_part.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", sa.String(36),
                  sa.ForeignKey("tb_team.id", ondelete="CASCADE"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("part_id", "team_id", name="uq_part_team"),
    )
    op.create_index("ix_tb_part_team_company_id", "tb_part_team", ["company_id"])
    op.create_index("ix_tb_part_team_part_id", "tb_part_team", ["part_id"])
    op.create_index("ix_tb_part_team_team_id", "tb_part_team", ["team_id"])

    op.create_table(
        "tb_part_asset",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("part_id", sa.String(36),
                  sa.ForeignKey("tb_part.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", sa.String(36),
                  sa.ForeignKey("tb_asset.id", ondelete="CASCADE"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("part_id", "asset_id", name="uq_part_asset"),
    )
    op.create_index("ix_tb_part_asset_company_id", "tb_part_asset", ["company_id"])
    op.create_index("ix_tb_part_asset_part_id", "tb_part_asset", ["part_id"])
    op.create_index("ix_tb_part_asset_asset_id", "tb_part_asset", ["asset_id"])


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("ix_tb_part_asset_asset_id", table_name="tb_part_asset")
        op.drop_index("ix_tb_part_asset_part_id", table_name="tb_part_asset")
        op.drop_index("ix_tb_part_asset_company_id", table_name="tb_part_asset")
    op.drop_table("tb_part_asset")
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("ix_tb_part_team_team_id", table_name="tb_part_team")
        op.drop_index("ix_tb_part_team_part_id", table_name="tb_part_team")
        op.drop_index("ix_tb_part_team_company_id", table_name="tb_part_team")
    op.drop_table("tb_part_team")
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("ix_tb_part_assignee_user_id", table_name="tb_part_assignee")
        op.drop_index("ix_tb_part_assignee_part_id", table_name="tb_part_assignee")
        op.drop_index("ix_tb_part_assignee_company_id", table_name="tb_part_assignee")
    op.drop_table("tb_part_assignee")
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("ix_tb_multi_part_item_part_id", table_name="tb_multi_part_item")
        op.drop_index("ix_tb_multi_part_item_multi_part_id", table_name="tb_multi_part_item")
        op.drop_index("ix_tb_multi_part_item_company_id", table_name="tb_multi_part_item")
    op.drop_table("tb_multi_part_item")
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("ix_tb_multi_part_company_id", table_name="tb_multi_part")
    op.drop_table("tb_multi_part")
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("ix_tb_part_consumption_work_order_id", table_name="tb_part_consumption")
        op.drop_index("ix_tb_part_consumption_part_id", table_name="tb_part_consumption")
        op.drop_index("ix_tb_part_consumption_company_id", table_name="tb_part_consumption")
    op.drop_table("tb_part_consumption")
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("ix_tb_part_category_id", table_name="tb_part")
        op.drop_index("ix_tb_part_company_id", table_name="tb_part")
    op.drop_table("tb_part")
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("ix_tb_part_category_company_id", table_name="tb_part_category")
    op.drop_table("tb_part_category")
