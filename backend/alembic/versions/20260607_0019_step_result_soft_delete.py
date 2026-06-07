"""work_order_step_result soft delete columns

Revision ID: step_result_soft_delete
Revises: custom_field
Create Date: 2026-06-07

手工撰写（MySQL 生产 + SQLite 开发/测试）。给 tb_work_order_step_result 加
is_active / deleted_at（SoftDeleteMixin），使其可作为通用 Attachment 宿主。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.models.base import DATETIME6

revision: str = "step_result_soft_delete"
down_revision: str | Sequence[str] | None = "custom_field"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tb_work_order_step_result") as batch_op:
        batch_op.add_column(
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch_op.add_column(sa.Column("deleted_at", DATETIME6, nullable=True))
        batch_op.create_index(
            "ix_tb_work_order_step_result_is_active", ["is_active"]
        )


def downgrade() -> None:
    with op.batch_alter_table("tb_work_order_step_result") as batch_op:
        batch_op.drop_index("ix_tb_work_order_step_result_is_active")
        batch_op.drop_column("deleted_at")
        batch_op.drop_column("is_active")
