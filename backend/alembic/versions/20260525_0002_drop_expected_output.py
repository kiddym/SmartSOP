"""drop expected_output from step

Revision ID: drop_expected_output
Revises: add_source_docx
Create Date: 2026-05-25
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = 'drop_expected_output'
down_revision: str | None = 'add_source_docx'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('tb_procedure_step') as batch:
        batch.drop_column('expected_output')


def downgrade() -> None:
    with op.batch_alter_table('tb_procedure_step') as batch:
        batch.add_column(sa.Column('expected_output', sa.Text(), nullable=False, server_default=sa.text("('')")))
