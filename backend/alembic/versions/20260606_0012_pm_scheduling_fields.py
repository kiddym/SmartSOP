"""pm scheduling fields: tb_preventive_maintenance 加排程增强字段

Revision ID: pm_scheduling_fields
Revises: part_rich_fields
Create Date: 2026-06-06

手工撰写（MySQL 生产 + SQLite 开发/测试）。
tb_preventive_maintenance 加 3 列（batch_alter_table，SQLite 表重建安全）：
  due_date_delay  生成工单 due_date 偏移天数（NOT NULL 默认 0）
  ends_on         排程结束日（可空；超期停生并自动停用）
  consecutive_unresponded  连续无人响应工单计数（NOT NULL 默认 0；失效自停信号）
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "pm_scheduling_fields"
down_revision: str | Sequence[str] | None = "part_rich_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tb_preventive_maintenance") as batch_op:
        batch_op.add_column(
            sa.Column(
                "due_date_delay",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(sa.Column("ends_on", sa.Date(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "consecutive_unresponded",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("tb_preventive_maintenance") as batch_op:
        batch_op.drop_column("consecutive_unresponded")
        batch_op.drop_column("ends_on")
        batch_op.drop_column("due_date_delay")
