"""add tb_heading_style_rule (动态标题字典 M1，单租户)

Revision ID: heading_style_rule
Revises: phase3c_purchase_order
Create Date: 2026-05-31

Hand-authored (MySQL prod + SQLite dev/test). New table -> create_table.
单租户：style_name 全局唯一；租户维度（company_id + 复合唯一）留待 P2。
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import DATETIME6

revision: str = "heading_style_rule"
down_revision: str | Sequence[str] | None = "phase3c_purchase_order"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tb_heading_style_rule",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("style_name", sa.String(255), nullable=False),
        sa.Column("level", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("level_votes", sa.JSON(), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("agreement", sa.Float(), nullable=False, server_default="0"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", DATETIME6, nullable=True),
        sa.UniqueConstraint("style_name", name="uq_heading_style_rule_style_name"),
    )


def downgrade() -> None:
    op.drop_table("tb_heading_style_rule")
