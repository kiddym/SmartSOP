"""part rich fields: tb_part 加 area/additional_infos

Revision ID: part_rich_fields
Revises: meter_rich_fields
Create Date: 2026-06-06

手工撰写（MySQL 生产 + SQLite 开发/测试）。
tb_part 加 2 个可空标量列（batch_alter_table，SQLite 表重建安全）：
  area(库区/货位) / additional_infos(附加信息)。
备件↔供应商/客户的 M:N 关联表（tb_vendor_part/tb_customer_part）已由既有
迁移建好，本迁移不涉及——备件侧仅对称维护既有关联表。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "part_rich_fields"
down_revision: str | Sequence[str] | None = "meter_rich_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tb_part") as batch_op:
        batch_op.add_column(sa.Column("area", sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column("additional_infos", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("tb_part") as batch_op:
        batch_op.drop_column("additional_infos")
        batch_op.drop_column("area")
