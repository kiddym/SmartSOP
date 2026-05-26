"""content block as step-level node

把 tb_procedure_chapter.content_type='content' 行搬到 tb_procedure_step
(kind='content')；step 加 kind 列；chapter 删 content_type/rich_content。
开发数据可重建，数据搬运为尽力而为的 1:1 直搬。

id 处理：迁出的 step.id 复用源 chapter.id（保持引用稳定——审计日志、版本快照
等外部表里 target_id 指向该 id 的记录在迁移后仍解析到等价实体）。downgrade
反向同理。
"""
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision: str = "content_block_as_step"
down_revision: str | None = "drop_step_require_confirmation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tb_procedure_step",
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="step"),
    )
    op.create_index("ix_tb_procedure_step_kind", "tb_procedure_step", ["kind"])

    bind = op.get_bind()
    now = datetime.utcnow()
    rows = bind.execute(
        sa.text(
            "SELECT id, procedure_id, parent_id, rich_content, sort_order, "
            "skip_numbering, is_active, deleted_at "
            "FROM tb_procedure_chapter WHERE content_type = 'content'"
        )
    ).fetchall()
    for r in rows:
        bind.execute(
            sa.text(
                "INSERT INTO tb_procedure_step "
                "(id, procedure_id, chapter_id, kind, title, code, content, "
                " sort_order, skip_numbering, input_schema, attachment_marks, "
                " is_active, deleted_at, created_at, updated_at) "
                "VALUES (:id, :pid, :cid, 'content', '', '', :content, :sort, "
                " :skip, '{}', '[]', :active, :deleted_at, :now, :now)"
            ),
            {
                "id": r.id,  # 复用源 chapter.id，保持外部引用稳定
                "pid": r.procedure_id,
                "cid": r.parent_id,
                "content": r.rich_content or "",
                "sort": r.sort_order,
                "skip": r.skip_numbering,
                "active": r.is_active,
                "deleted_at": r.deleted_at,
                "now": now,
            },
        )
    bind.execute(sa.text("DELETE FROM tb_procedure_chapter WHERE content_type = 'content'"))

    op.drop_index("ix_tb_procedure_chapter_content_type", table_name="tb_procedure_chapter")
    op.drop_column("tb_procedure_chapter", "content_type")
    op.drop_column("tb_procedure_chapter", "rich_content")


def downgrade() -> None:
    op.add_column(
        "tb_procedure_chapter",
        sa.Column("content_type", sa.String(length=20), nullable=False, server_default="chapter"),
    )
    op.add_column(
        "tb_procedure_chapter",
        sa.Column("rich_content", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index(
        "ix_tb_procedure_chapter_content_type", "tb_procedure_chapter", ["content_type"]
    )

    bind = op.get_bind()
    now = datetime.utcnow()
    rows = bind.execute(
        sa.text(
            "SELECT id, procedure_id, chapter_id, content, sort_order, skip_numbering, "
            "is_active, deleted_at FROM tb_procedure_step WHERE kind = 'content'"
        )
    ).fetchall()
    for r in rows:
        bind.execute(
            sa.text(
                "INSERT INTO tb_procedure_chapter "
                "(id, procedure_id, parent_id, content_type, title, code, rich_content, "
                " sort_order, level, mark_status, skip_numbering, conversion_status, "
                " is_active, deleted_at, created_at, updated_at) "
                "VALUES (:id, :pid, :cid, 'content', '', '', :content, :sort, 1, "
                " 'unmarked', :skip, 'applied', :active, :deleted_at, :now, :now)"
            ),
            {
                "id": r.id,  # 复用源 step.id，对称于 upgrade
                "pid": r.procedure_id,
                "cid": r.chapter_id,
                "content": r.content or "",
                "sort": r.sort_order,
                "skip": r.skip_numbering,
                "active": r.is_active,
                "deleted_at": r.deleted_at,
                "now": now,
            },
        )
    bind.execute(sa.text("DELETE FROM tb_procedure_step WHERE kind = 'content'"))

    op.drop_index("ix_tb_procedure_step_kind", table_name="tb_procedure_step")
    op.drop_column("tb_procedure_step", "kind")
