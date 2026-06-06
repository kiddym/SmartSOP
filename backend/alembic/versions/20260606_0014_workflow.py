"""workflow: tb_workflow 工单触发规则引擎表

Revision ID: workflow
Revises: po_customer_fields
Create Date: 2026-06-06

手工撰写（MySQL 生产 + SQLite 开发/测试）。
新建 tb_workflow（UUIDMixin + TimestampMixin + TenantMixin）：
  name(String 必填) / enabled(bool 默认 True) / trigger(String 必填) /
  conditions(JSON 列表) / actions(JSON 列表)。
conditions/actions 用 sa.JSON()（MySQL→JSON，SQLite→TEXT）。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "workflow"
down_revision: str | Sequence[str] | None = "po_customer_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tb_workflow",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("trigger", sa.String(length=48), nullable=False),
        sa.Column("conditions", sa.JSON(), nullable=False),
        sa.Column("actions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["tb_company.id"],
            name=op.f("fk_tb_workflow_company_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tb_workflow")),
    )
    op.create_index(op.f("ix_tb_workflow_company_id"), "tb_workflow", ["company_id"], unique=False)
    op.create_index(op.f("ix_tb_workflow_created_at"), "tb_workflow", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tb_workflow_created_at"), table_name="tb_workflow")
    op.drop_index(op.f("ix_tb_workflow_company_id"), table_name="tb_workflow")
    op.drop_table("tb_workflow")
