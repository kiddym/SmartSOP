"""platform account/config: password reset token / user invitation /
company settings / global currency tables + email_outbox nullable recipient

Revision ID: platform_account_config
Revises: add_batch_import
Create Date: 2026-06-02

Hand-authored (MySQL prod + SQLite dev/test). Adds the platform account &
configuration backfill tables and relaxes
``tb_email_outbox.recipient_user_id`` to NULLABLE (transactional emails such as
password-reset / invitation have no resident recipient user yet).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.models.base import DATETIME6

revision: str = "platform_account_config"
down_revision: str | Sequence[str] | None = "add_batch_import"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- tb_password_reset_token (TenantMixin) --------------------------------
    op.create_table(
        "tb_password_reset_token",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", DATETIME6, nullable=False),
        sa.Column("used_at", DATETIME6, nullable=True),
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["tb_company.id"],
            name="fk_tb_password_reset_token_company_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["tb_user.id"],
            name="fk_tb_password_reset_token_user_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tb_password_reset_token"),
    )
    op.create_index(
        "ix_tb_password_reset_token_company_id", "tb_password_reset_token", ["company_id"]
    )
    op.create_index(
        "ix_tb_password_reset_token_user_id", "tb_password_reset_token", ["user_id"]
    )
    op.create_index(
        "ix_tb_password_reset_token_token_hash", "tb_password_reset_token", ["token_hash"]
    )
    op.create_index(
        "ix_tb_password_reset_token_created_at", "tb_password_reset_token", ["created_at"]
    )

    # --- tb_user_invitation (TenantMixin) -------------------------------------
    op.create_table(
        "tb_user_invitation",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("role_id", sa.String(length=36), nullable=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", DATETIME6, nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("invited_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["tb_company.id"],
            name="fk_tb_user_invitation_company_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["tb_role.id"],
            name="fk_tb_user_invitation_role_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tb_user_invitation"),
    )
    op.create_index("ix_tb_user_invitation_company_id", "tb_user_invitation", ["company_id"])
    op.create_index("ix_tb_user_invitation_email", "tb_user_invitation", ["email"])
    op.create_index("ix_tb_user_invitation_token_hash", "tb_user_invitation", ["token_hash"])
    op.create_index("ix_tb_user_invitation_created_at", "tb_user_invitation", ["created_at"])

    # --- tb_company_settings (TenantMixin, singleton per company) -------------
    op.create_table(
        "tb_company_settings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column(
            "date_format", sa.String(length=32), nullable=False, server_default="YYYY-MM-DD"
        ),
        sa.Column(
            "timezone", sa.String(length=64), nullable=False, server_default="Asia/Shanghai"
        ),
        sa.Column(
            "default_currency_code",
            sa.String(length=8),
            nullable=False,
            server_default="CNY",
        ),
        sa.Column("auto_assign", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["tb_company.id"],
            name="fk_tb_company_settings_company_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tb_company_settings"),
        sa.UniqueConstraint("company_id", name="uq_company_settings_company"),
    )
    op.create_index("ix_tb_company_settings_company_id", "tb_company_settings", ["company_id"])
    op.create_index("ix_tb_company_settings_created_at", "tb_company_settings", ["created_at"])

    # --- tb_currency (global; no tenant scoping) ------------------------------
    op.create_table(
        "tb_currency",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=8), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=8), nullable=False, server_default=""),
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_tb_currency"),
    )
    op.create_index("ix_tb_currency_code", "tb_currency", ["code"], unique=True)
    op.create_index("ix_tb_currency_created_at", "tb_currency", ["created_at"])

    # --- tb_email_outbox.recipient_user_id -> NULLABLE ------------------------
    with op.batch_alter_table("tb_email_outbox") as batch_op:
        batch_op.alter_column(
            "recipient_user_id",
            existing_type=sa.String(length=36),
            nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("tb_email_outbox") as batch_op:
        batch_op.alter_column(
            "recipient_user_id",
            existing_type=sa.String(length=36),
            nullable=False,
        )

    op.drop_index("ix_tb_currency_created_at", table_name="tb_currency")
    op.drop_index("ix_tb_currency_code", table_name="tb_currency")
    op.drop_table("tb_currency")

    op.drop_index("ix_tb_company_settings_created_at", table_name="tb_company_settings")
    op.drop_index("ix_tb_company_settings_company_id", table_name="tb_company_settings")
    op.drop_table("tb_company_settings")

    op.drop_index("ix_tb_user_invitation_created_at", table_name="tb_user_invitation")
    op.drop_index("ix_tb_user_invitation_token_hash", table_name="tb_user_invitation")
    op.drop_index("ix_tb_user_invitation_email", table_name="tb_user_invitation")
    op.drop_index("ix_tb_user_invitation_company_id", table_name="tb_user_invitation")
    op.drop_table("tb_user_invitation")

    op.drop_index(
        "ix_tb_password_reset_token_created_at", table_name="tb_password_reset_token"
    )
    op.drop_index(
        "ix_tb_password_reset_token_token_hash", table_name="tb_password_reset_token"
    )
    op.drop_index("ix_tb_password_reset_token_user_id", table_name="tb_password_reset_token")
    op.drop_index(
        "ix_tb_password_reset_token_company_id", table_name="tb_password_reset_token"
    )
    op.drop_table("tb_password_reset_token")
