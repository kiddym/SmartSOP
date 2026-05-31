"""add tb_numbering_profile (numbering convention overrides, M4b)

按 pattern_key 覆盖内置编号判定(kind/level)。解析时读 status='active' 拼 numbering_overrides
注入 parse_docx。M4b 仅 source='manual';投票列预留给后续编号自学习。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "add_numbering_profile"
down_revision: str | None = "add_heading_learning_event"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tb_numbering_profile",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("pattern_key", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="heading"),
        sa.Column("level", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("level_votes", sa.JSON(), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("agreement", sa.Float(), nullable=False, server_default="0"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_tb_numbering_profile"),
        sa.UniqueConstraint("pattern_key", name="uq_tb_numbering_profile_pattern_key"),
    )
    op.create_index("ix_tb_numbering_profile_is_active", "tb_numbering_profile", ["is_active"])
    op.create_index("ix_tb_numbering_profile_created_at", "tb_numbering_profile", ["created_at"])
    op.create_index("ix_tb_numbering_profile_status", "tb_numbering_profile", ["status"])


def downgrade() -> None:
    op.drop_index("ix_tb_numbering_profile_status", table_name="tb_numbering_profile")
    op.drop_index("ix_tb_numbering_profile_created_at", table_name="tb_numbering_profile")
    op.drop_index("ix_tb_numbering_profile_is_active", table_name="tb_numbering_profile")
    op.drop_table("tb_numbering_profile")
