"""phase5a notification tables

Revision ID: phase5a_notification
Revises: po_line_no
Create Date: 2026-05-31

站内通知（Phase 5A）：通知行 tb_notification + 边沿状态行 tb_notification_arm。
append-only 无软删。Hand-authored（MySQL prod + SQLite dev/test）。
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import DATETIME6

revision: str = "phase5a_notification"
down_revision: str | Sequence[str] | None = "po_line_no"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ts() -> list[sa.Column]:
    return [
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
    ]


def _company_fk() -> sa.Column:
    return sa.Column(
        "company_id", sa.String(36),
        sa.ForeignKey("tb_company.id", ondelete="CASCADE"), nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "tb_notification",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        *_ts(),
        sa.Column("recipient_user_id", sa.String(36), nullable=False),
        sa.Column("type", sa.String(40), nullable=False),
        sa.Column("entity_type", sa.String(40), nullable=True),
        sa.Column("entity_id", sa.String(36), nullable=True),
        sa.Column("params", sa.Text(), nullable=False, server_default=sa.text("('{}')")),
        sa.Column("actor_user_id", sa.String(36), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("read_at", DATETIME6, nullable=True),
        sa.Column("dedup_key", sa.String(120), nullable=True),
    )
    op.create_index("ix_tb_notification_company_id", "tb_notification", ["company_id"])
    op.create_index("ix_tb_notification_created_at", "tb_notification", ["created_at"])
    op.create_index("ix_tb_notification_recipient_user_id", "tb_notification", ["recipient_user_id"])
    op.create_index("ix_tb_notification_is_read", "tb_notification", ["is_read"])
    op.create_index("ix_tb_notification_recipient_read", "tb_notification",
                    ["company_id", "recipient_user_id", "is_read"])
    op.create_index("ix_tb_notification_dedup", "tb_notification",
                    ["company_id", "dedup_key"])

    op.create_table(
        "tb_notification_arm",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        *_ts(),
        sa.Column("key", sa.String(120), nullable=False),
        sa.UniqueConstraint("company_id", "key", name="uq_notification_arm"),
    )
    op.create_index("ix_tb_notification_arm_company_id", "tb_notification_arm", ["company_id"])
    op.create_index("ix_tb_notification_arm_created_at", "tb_notification_arm", ["created_at"])


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("ix_tb_notification_arm_created_at", table_name="tb_notification_arm")
        op.drop_index("ix_tb_notification_arm_company_id", table_name="tb_notification_arm")
    op.drop_table("tb_notification_arm")
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("ix_tb_notification_dedup", table_name="tb_notification")
        op.drop_index("ix_tb_notification_recipient_read", table_name="tb_notification")
        op.drop_index("ix_tb_notification_is_read", table_name="tb_notification")
        op.drop_index("ix_tb_notification_recipient_user_id", table_name="tb_notification")
        op.drop_index("ix_tb_notification_created_at", table_name="tb_notification")
        op.drop_index("ix_tb_notification_company_id", table_name="tb_notification")
    op.drop_table("tb_notification")
