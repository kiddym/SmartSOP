"""add alert schemas to step

Revision ID: add_alert_schemas_step
Revises: add_settings_revision
Create Date: 2026-05-23

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = 'add_alert_schemas_step'
down_revision: str | None = 'add_settings_revision'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'tb_procedure_step',
        sa.Column('note_schema', sa.JSON(), nullable=False, server_default='{"type": "COMMON"}'),
    )
    op.add_column(
        'tb_procedure_step',
        sa.Column('caution_schema', sa.JSON(), nullable=False, server_default='{"type": "COMMON"}'),
    )
    op.add_column(
        'tb_procedure_step',
        sa.Column('warning_schema', sa.JSON(), nullable=False, server_default='{"type": "COMMON"}'),
    )


def downgrade() -> None:
    op.drop_column('tb_procedure_step', 'warning_schema')
    op.drop_column('tb_procedure_step', 'caution_schema')
    op.drop_column('tb_procedure_step', 'note_schema')
