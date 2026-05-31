"""add tb_heading_style_rule (dynamic heading dictionary, M1)

动态标题字典-样式规则表。解析时读 status='active' 规则拼 style_overrides 注入 parse_docx。
M1 仅 source='manual'（手动维护即时生效）；投票列（level_votes/evidence_count/agreement）
预留给 M3 自学习，避免二次迁移。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "add_heading_style_rule"
down_revision: str | None = "drop_legacy_chapter_step"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tb_heading_style_rule",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("style_name", sa.String(length=255), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="pk_tb_heading_style_rule"),
        sa.UniqueConstraint("style_name", name="uq_tb_heading_style_rule_style_name"),
    )
    op.create_index(
        "ix_tb_heading_style_rule_is_active", "tb_heading_style_rule", ["is_active"]
    )
    op.create_index(
        "ix_tb_heading_style_rule_created_at", "tb_heading_style_rule", ["created_at"]
    )
    op.create_index("ix_tb_heading_style_rule_status", "tb_heading_style_rule", ["status"])


def downgrade() -> None:
    op.drop_index("ix_tb_heading_style_rule_status", table_name="tb_heading_style_rule")
    op.drop_index("ix_tb_heading_style_rule_created_at", table_name="tb_heading_style_rule")
    op.drop_index("ix_tb_heading_style_rule_is_active", table_name="tb_heading_style_rule")
    op.drop_table("tb_heading_style_rule")
