"""phase5b email + storage tables

Revision ID: phase5b_email_storage
Revises: procedure_import_notes
Create Date: 2026-05-31

Phase 5B：邮件偏好 tb_notification_preference + 投递队列 tb_email_outbox。
存储子系统零迁移（DB schema 不变）。Hand-authored（MySQL prod + SQLite dev/test）。
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import DATETIME6

revision: str = "phase5b_email_storage"
down_revision: str | Sequence[str] | None = "procedure_import_notes"
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
        "tb_notification_preference",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        *_ts(),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("disabled_types", sa.Text(), nullable=False, server_default=sa.text("('[]')")),
        sa.UniqueConstraint("company_id", "user_id", name="uq_notif_pref_user"),
    )
    op.create_index("ix_tb_notification_preference_company_id",
                    "tb_notification_preference", ["company_id"])
    op.create_index("ix_tb_notification_preference_created_at",
                    "tb_notification_preference", ["created_at"])
    op.create_index("ix_tb_notification_preference_user_id",
                    "tb_notification_preference", ["user_id"])

    op.create_table(
        "tb_email_outbox",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        *_ts(),
        sa.Column("recipient_user_id", sa.String(36), nullable=False),
        sa.Column("recipient_email", sa.String(255), nullable=False),
        sa.Column("type", sa.String(40), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("sent_at", DATETIME6, nullable=True),
        sa.Column("notification_id", sa.String(36), nullable=True),
    )
    op.create_index("ix_tb_email_outbox_company_id", "tb_email_outbox", ["company_id"])
    op.create_index("ix_tb_email_outbox_created_at", "tb_email_outbox", ["created_at"])
    op.create_index("ix_tb_email_outbox_recipient_user_id", "tb_email_outbox",
                    ["recipient_user_id"])
    op.create_index("ix_email_outbox_status", "tb_email_outbox", ["company_id", "status"])


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("ix_email_outbox_status", table_name="tb_email_outbox")
        op.drop_index("ix_tb_email_outbox_recipient_user_id", table_name="tb_email_outbox")
        op.drop_index("ix_tb_email_outbox_created_at", table_name="tb_email_outbox")
        op.drop_index("ix_tb_email_outbox_company_id", table_name="tb_email_outbox")
    op.drop_table("tb_email_outbox")
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("ix_tb_notification_preference_user_id",
                      table_name="tb_notification_preference")
        op.drop_index("ix_tb_notification_preference_created_at",
                      table_name="tb_notification_preference")
        op.drop_index("ix_tb_notification_preference_company_id",
                      table_name="tb_notification_preference")
    op.drop_table("tb_notification_preference")
