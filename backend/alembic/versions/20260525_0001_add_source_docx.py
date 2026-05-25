"""add tb_procedure_source_docx

Revision ID: add_source_docx
Revises: drop_alert_fields
Create Date: 2026-05-25
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = 'add_source_docx'
down_revision: str | None = 'drop_alert_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'tb_procedure_source_docx',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('procedure_group_id', sa.String(length=64), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('storage_path', sa.String(length=500), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), 'mysql'), nullable=False),
        sa.Column('updated_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), 'mysql'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_tb_procedure_source_docx')),
    )
    op.create_index(op.f('ix_tb_procedure_source_docx_created_at'), 'tb_procedure_source_docx', ['created_at'], unique=False)
    op.create_index('uq_tb_procedure_source_docx_procedure_group_id', 'tb_procedure_source_docx', ['procedure_group_id'], unique=True)


def downgrade() -> None:
    op.drop_index('uq_tb_procedure_source_docx_procedure_group_id', table_name='tb_procedure_source_docx')
    op.drop_index(op.f('ix_tb_procedure_source_docx_created_at'), table_name='tb_procedure_source_docx')
    op.drop_table('tb_procedure_source_docx')
