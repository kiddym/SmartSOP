"""push token + super account relation + email verification

Revision ID: push_switch_verify
Revises: attachment_hidden_type
Create Date: 2026-06-06

手工撰写（MySQL 生产 + SQLite 开发/测试）。I 尾项最后一批 3 个低优先项：
- tb_push_token：移动端推送 token（每用户多设备，唯一 (user_id, token)）；
- tb_super_account_relation：切换账户授权白名单（唯一 (super_user_id, target_company_id)）；
- tb_verification_token：邮箱验证 token（仿密码重置，单次/限时/存哈希）；
- tb_user 加 email_verified（既有行回填 True：纯信息标记、不门控任何功能，
  对老用户视作"已验证"避免在 UI 上无故标红，新注册行默认 False 由验证流程置真）。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.models.base import DATETIME6

revision: str = "push_switch_verify"
down_revision: str | Sequence[str] | None = "attachment_hidden_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- tb_push_token ---
    op.create_table(
        "tb_push_token",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(length=36),
            sa.ForeignKey("tb_company.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("tb_user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token", sa.String(length=512), nullable=False),
        sa.Column("platform", sa.String(length=16), nullable=False),
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
        sa.UniqueConstraint("user_id", "token", name="uq_push_token_user_token"),
    )
    op.create_index("ix_tb_push_token_company_id", "tb_push_token", ["company_id"])
    op.create_index("ix_tb_push_token_user_id", "tb_push_token", ["user_id"])
    op.create_index("ix_tb_push_token_created_at", "tb_push_token", ["created_at"])

    # --- tb_super_account_relation ---
    op.create_table(
        "tb_super_account_relation",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(length=36),
            sa.ForeignKey("tb_company.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "super_user_id",
            sa.String(length=36),
            sa.ForeignKey("tb_user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_company_id",
            sa.String(length=36),
            sa.ForeignKey("tb_company.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
        sa.UniqueConstraint("super_user_id", "target_company_id", name="uq_super_account_relation"),
    )
    op.create_index(
        "ix_tb_super_account_relation_company_id",
        "tb_super_account_relation",
        ["company_id"],
    )
    op.create_index(
        "ix_tb_super_account_relation_super_user_id",
        "tb_super_account_relation",
        ["super_user_id"],
    )
    op.create_index(
        "ix_tb_super_account_relation_target_company_id",
        "tb_super_account_relation",
        ["target_company_id"],
    )
    op.create_index(
        "ix_tb_super_account_relation_created_at",
        "tb_super_account_relation",
        ["created_at"],
    )

    # --- tb_verification_token ---
    op.create_table(
        "tb_verification_token",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(length=36),
            sa.ForeignKey("tb_company.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("tb_user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", DATETIME6, nullable=False),
        sa.Column("used_at", DATETIME6, nullable=True),
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
    )
    op.create_index("ix_tb_verification_token_company_id", "tb_verification_token", ["company_id"])
    op.create_index("ix_tb_verification_token_user_id", "tb_verification_token", ["user_id"])
    op.create_index("ix_tb_verification_token_token_hash", "tb_verification_token", ["token_hash"])
    op.create_index("ix_tb_verification_token_created_at", "tb_verification_token", ["created_at"])

    # --- tb_user.email_verified（既有行回填 True；新行默认 False） ---
    with op.batch_alter_table("tb_user") as batch_op:
        batch_op.add_column(
            sa.Column(
                "email_verified",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )
    # 回填后把默认改回 False，使 ORM 默认（新注册未验证）一致。
    with op.batch_alter_table("tb_user") as batch_op:
        batch_op.alter_column(
            "email_verified",
            existing_type=sa.Boolean(),
            server_default=sa.false(),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("tb_user") as batch_op:
        batch_op.drop_column("email_verified")

    is_sqlite = op.get_bind().dialect.name == "sqlite"
    if is_sqlite:
        op.drop_index("ix_tb_verification_token_created_at", table_name="tb_verification_token")
        op.drop_index("ix_tb_verification_token_token_hash", table_name="tb_verification_token")
        op.drop_index("ix_tb_verification_token_user_id", table_name="tb_verification_token")
        op.drop_index("ix_tb_verification_token_company_id", table_name="tb_verification_token")
    op.drop_table("tb_verification_token")

    if is_sqlite:
        op.drop_index(
            "ix_tb_super_account_relation_created_at",
            table_name="tb_super_account_relation",
        )
        op.drop_index(
            "ix_tb_super_account_relation_target_company_id",
            table_name="tb_super_account_relation",
        )
        op.drop_index(
            "ix_tb_super_account_relation_super_user_id",
            table_name="tb_super_account_relation",
        )
        op.drop_index(
            "ix_tb_super_account_relation_company_id",
            table_name="tb_super_account_relation",
        )
    op.drop_table("tb_super_account_relation")

    if is_sqlite:
        op.drop_index("ix_tb_push_token_created_at", table_name="tb_push_token")
        op.drop_index("ix_tb_push_token_user_id", table_name="tb_push_token")
        op.drop_index("ix_tb_push_token_company_id", table_name="tb_push_token")
    op.drop_table("tb_push_token")
