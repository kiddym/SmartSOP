"""tb_purchase_order_line.line_no（录入行序，稳定排序）

Revision ID: po_line_no
Revises: dict_tenantization
Create Date: 2026-05-31

PO 明细行加 line_no（0-based 录入顺序），使 lines() 按录入序稳定排序，
取代原先按随机 UUID id 排序导致的非确定性。既有行回填 0（server_default）。
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "po_line_no"
down_revision: str | Sequence[str] | None = "dict_tenantization"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tb_purchase_order_line",
        sa.Column("line_no", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("tb_purchase_order_line", "line_no")
