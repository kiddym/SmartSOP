"""add tb_heading_learning_event (implicit learning signals, M3)

append-only 学习信号表。编辑器对样式标题的改级/互转/确认 → 一条事件;聚合器按文档
最新投票推导 learned 规则(heading_learning_service)。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "add_heading_learning_event"
down_revision: str | None = "add_node_source_style_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tb_heading_learning_event",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("procedure_id", sa.String(length=36), nullable=False),
        sa.Column("node_id", sa.String(length=36), nullable=False),
        sa.Column("style_name", sa.String(length=255), nullable=False),
        sa.Column("signal_type", sa.String(length=30), nullable=False),
        sa.Column("from_level", sa.Integer(), nullable=True),
        sa.Column("to_level", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_tb_heading_learning_event"),
    )
    op.create_index(
        "ix_tb_heading_learning_event_procedure_id",
        "tb_heading_learning_event",
        ["procedure_id"],
    )
    op.create_index(
        "ix_tb_heading_learning_event_style_name",
        "tb_heading_learning_event",
        ["style_name"],
    )
    op.create_index(
        "ix_tb_heading_learning_event_style_name_procedure_id",
        "tb_heading_learning_event",
        ["style_name", "procedure_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tb_heading_learning_event_style_name_procedure_id",
        table_name="tb_heading_learning_event",
    )
    op.drop_index(
        "ix_tb_heading_learning_event_style_name", table_name="tb_heading_learning_event"
    )
    op.drop_index(
        "ix_tb_heading_learning_event_procedure_id", table_name="tb_heading_learning_event"
    )
    op.drop_table("tb_heading_learning_event")
