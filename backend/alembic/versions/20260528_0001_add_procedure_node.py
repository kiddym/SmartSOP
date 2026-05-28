"""add tb_procedure_node (unified node model, Plan A)

新增 tb_procedure_node 表,与 tb_procedure_chapter/tb_procedure_step 并存。
不搬数据(开发数据可重建);旧表删除在 Plan B。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "add_procedure_node"
down_revision: str | None = "content_block_as_step"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tb_procedure_node",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("procedure_id", sa.String(length=36), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("heading_level", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="node"),
        sa.Column(
            "body",
            sa.Text().with_variant(mysql.LONGTEXT(), "mysql"),
            nullable=False,
            server_default="",
        ),
        sa.Column("code", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("skip_numbering", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("input_schema", sa.JSON(), nullable=False),
        sa.Column("attachment_marks", sa.JSON(), nullable=False),
        sa.Column("mark_status", sa.String(length=20), nullable=False, server_default="unmarked"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["procedure_id"], ["tb_procedure.id"],
            name="fk_tb_procedure_node_procedure_id", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tb_procedure_node"),
    )
    op.create_index(
        "ix_tb_procedure_node_procedure_id_sort_order",
        "tb_procedure_node", ["procedure_id", "sort_order"],
    )
    op.create_index(
        "ix_tb_procedure_node_mark_status", "tb_procedure_node", ["mark_status"]
    )
    op.create_index("ix_tb_procedure_node_is_active", "tb_procedure_node", ["is_active"])
    op.create_index("ix_tb_procedure_node_created_at", "tb_procedure_node", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_tb_procedure_node_created_at", table_name="tb_procedure_node")
    op.drop_index("ix_tb_procedure_node_is_active", table_name="tb_procedure_node")
    op.drop_index("ix_tb_procedure_node_mark_status", table_name="tb_procedure_node")
    op.drop_index(
        "ix_tb_procedure_node_procedure_id_sort_order", table_name="tb_procedure_node"
    )
    op.drop_table("tb_procedure_node")
