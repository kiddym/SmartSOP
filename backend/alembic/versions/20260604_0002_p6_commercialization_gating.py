"""P6 commercialization gating: backfill plan/subscription_status + server_default.

Revision ID: p6_commercialization_gating
Revises: workorder_2b_backfill
Create Date: 2026-06-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "p6_commercialization_gating"
down_revision = "workorder_2b_backfill"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) backfill 存量 NULL → free/active
    op.execute("UPDATE tb_company SET plan = 'free' WHERE plan IS NULL")
    op.execute(
        "UPDATE tb_company SET subscription_status = 'active' "
        "WHERE subscription_status IS NULL"
    )
    # 2) 设 server_default + NOT NULL
    with op.batch_alter_table("tb_company") as batch:
        batch.alter_column(
            "plan",
            existing_type=sa.String(length=32),
            server_default="free",
            nullable=False,
        )
        batch.alter_column(
            "subscription_status",
            existing_type=sa.String(length=32),
            server_default="active",
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("tb_company") as batch:
        batch.alter_column(
            "subscription_status",
            existing_type=sa.String(length=32),
            server_default=None,
            nullable=True,
        )
        batch.alter_column(
            "plan",
            existing_type=sa.String(length=32),
            server_default=None,
            nullable=True,
        )
