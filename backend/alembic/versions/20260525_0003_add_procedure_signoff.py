"""add signoff_enabled to procedure

Revision ID: add_procedure_signoff
Revises: drop_expected_output
Create Date: 2026-05-25
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = 'add_procedure_signoff'
down_revision: str | None = 'drop_expected_output'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('tb_procedure') as batch:
        batch.add_column(sa.Column('signoff_enabled', sa.Boolean(), server_default='0', nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('tb_procedure') as batch:
        batch.drop_column('signoff_enabled')
