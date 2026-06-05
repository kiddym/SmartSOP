"""P6 stripe billing: company stripe ids + billing event dedup table

Revision ID: p6_stripe_billing
Revises: sop_tenancy_hardening
Create Date: 2026-06-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.models.base import DATETIME6

revision: str = "p6_stripe_billing"
down_revision: str | Sequence[str] | None = "sop_tenancy_hardening"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tb_company") as b:
        b.add_column(sa.Column("stripe_customer_id", sa.String(length=255), nullable=True))
        b.add_column(sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True))
        b.create_unique_constraint("uq_tb_company_stripe_customer_id", ["stripe_customer_id"])

    op.create_table(
        "tb_billing_event",
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("processed_at", DATETIME6, nullable=False),
        sa.PrimaryKeyConstraint("event_id", name=op.f("pk_tb_billing_event")),
    )


def downgrade() -> None:
    op.drop_table("tb_billing_event")
    with op.batch_alter_table("tb_company") as b:
        b.drop_constraint("uq_tb_company_stripe_customer_id", type_="unique")
        b.drop_column("stripe_subscription_id")
        b.drop_column("stripe_customer_id")
