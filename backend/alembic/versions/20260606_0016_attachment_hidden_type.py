"""attachment hidden + file_type: tb_attachment 加 hidden(bool)/file_type(短枚举)

Revision ID: attachment_hidden_type
Revises: wo_misc_fields
Create Date: 2026-06-06

手工撰写（MySQL 生产 + SQLite 开发/测试）。
tb_attachment 加 2 个带默认的标量列（batch_alter_table，SQLite 表重建安全）：
  hidden(NOT NULL, default false)：全局文件库软隐藏标记；
  file_type(NOT NULL, default 'OTHER')：文件大类（IMAGE/OTHER），上传时按 MIME 推断。
存量行由 server_default 回填（hidden→false，file_type→'OTHER'）。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "attachment_hidden_type"
down_revision: str | Sequence[str] | None = "wo_misc_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tb_attachment") as batch_op:
        batch_op.add_column(
            sa.Column(
                "file_type",
                sa.String(length=16),
                nullable=False,
                server_default="OTHER",
            )
        )
        batch_op.add_column(
            sa.Column(
                "hidden",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("tb_attachment") as batch_op:
        batch_op.drop_column("hidden")
        batch_op.drop_column("file_type")
