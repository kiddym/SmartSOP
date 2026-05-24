"""drop alert fields, backfill content

Revision ID: drop_alert_fields
Revises: add_alert_schemas_step
Create Date: 2026-05-24
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = 'drop_alert_fields'
down_revision: str | None = 'add_alert_schemas_step'
branch_labels = None
depends_on = None

_ALERT_COLS = ('note', 'caution', 'warning', 'note_schema', 'caution_schema', 'warning_schema')


def upgrade() -> None:
    # 回填：把旧三警示 HTML 追加进 content。Alembic 版本表保证整体只跑一次；
    # 即便重跑，旧列清空后 new_content==content，不会重复追加。
    bind = op.get_bind()
    rows = bind.execute(sa.text(
        "SELECT id, content, note, caution, warning FROM tb_procedure_step"
    )).mappings().all()
    for r in rows:
        parts = []
        if (r['content'] or '').strip():
            parts.append(r['content'])
        for label in ('note', 'caution', 'warning'):
            v = (r[label] or '').strip()
            if v:
                parts.append(f'<div class="{label}-block">{v}</div>')
        new_content = ''.join(parts)
        if new_content != (r['content'] or ''):
            bind.execute(
                sa.text("UPDATE tb_procedure_step SET content = :c WHERE id = :i"),
                {"c": new_content, "i": r['id']},
            )
    with op.batch_alter_table('tb_procedure_step') as batch:
        for col in _ALERT_COLS:
            batch.drop_column(col)


def downgrade() -> None:
    with op.batch_alter_table('tb_procedure_step') as batch:
        batch.add_column(sa.Column('note', sa.Text(), nullable=False, server_default=''))
        batch.add_column(sa.Column('caution', sa.Text(), nullable=False, server_default=''))
        batch.add_column(sa.Column('warning', sa.Text(), nullable=False, server_default=''))
        batch.add_column(sa.Column('note_schema', sa.JSON(), nullable=False, server_default='{"type": "COMMON"}'))
        batch.add_column(sa.Column('caution_schema', sa.JSON(), nullable=False, server_default='{"type": "COMMON"}'))
        batch.add_column(sa.Column('warning_schema', sa.JSON(), nullable=False, server_default='{"type": "COMMON"}'))
