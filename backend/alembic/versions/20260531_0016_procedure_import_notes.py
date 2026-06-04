"""add import_notes to procedure

Revision ID: procedure_import_notes
Revises: phase5a_notification
Create Date: 2026-05-31

A 项：导入时刻解析 warnings 快照（强确认 + 编辑器常驻提示区）。
Hand-authored（MySQL prod + SQLite dev/test）。
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = "procedure_import_notes"
down_revision: str | None = "phase5a_notification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tb_procedure") as batch:
        batch.add_column(
            sa.Column("import_notes", sa.JSON(), nullable=False, server_default=sa.text("('[]')"))
        )


def downgrade() -> None:
    with op.batch_alter_table("tb_procedure") as batch:
        batch.drop_column("import_notes")
