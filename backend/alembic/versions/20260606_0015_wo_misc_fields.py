"""work order misc fields:
- tb_work_order_labor 加 include_to_total
- tb_work_order_additional_cost 加 include_to_total
- tb_work_order 加 signature_url + required_signature

Revision ID: wo_misc_fields
Revises: workflow
Create Date: 2026-06-06

手工撰写（MySQL 生产 + SQLite 开发/测试）。全部为可空/带默认的标量列，
batch_alter_table（SQLite 表重建安全）。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "wo_misc_fields"
down_revision: str | Sequence[str] | None = "workflow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tb_work_order_labor") as batch_op:
        batch_op.add_column(
            sa.Column(
                "include_to_total",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )
    with op.batch_alter_table("tb_work_order_additional_cost") as batch_op:
        batch_op.add_column(
            sa.Column(
                "include_to_total",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )
    with op.batch_alter_table("tb_work_order") as batch_op:
        batch_op.add_column(sa.Column("signature_url", sa.String(length=512), nullable=True))
        batch_op.add_column(
            sa.Column(
                "required_signature",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("tb_work_order") as batch_op:
        batch_op.drop_column("required_signature")
        batch_op.drop_column("signature_url")
    with op.batch_alter_table("tb_work_order_additional_cost") as batch_op:
        batch_op.drop_column("include_to_total")
    with op.batch_alter_table("tb_work_order_labor") as batch_op:
        batch_op.drop_column("include_to_total")
