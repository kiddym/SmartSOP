"""add tb_procedure_node.source_style_name (heading dictionary learning, M2)

样式标题导入时持久化来源样式名,供编辑器「记住此样式」反查归因。nullable;
零样式编号标题/正文为 null。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "add_node_source_style_name"
down_revision: str | None = "add_heading_style_rule"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tb_procedure_node",
        sa.Column("source_style_name", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tb_procedure_node", "source_style_name")
