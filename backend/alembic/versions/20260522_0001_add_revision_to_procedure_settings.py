"""add revision to procedure settings

Revision ID: add_settings_revision
Revises: 1d3b3aad6681
Create Date: 2026-05-22

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = 'add_settings_revision'
down_revision: str | None = '1d3b3aad6681'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'tb_procedure_settings',
        sa.Column('revision', sa.Integer(), server_default='0', nullable=False),
    )


def downgrade() -> None:
    op.drop_column('tb_procedure_settings', 'revision')
