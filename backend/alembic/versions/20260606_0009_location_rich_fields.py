"""location rich fields: tb_location 加 image_url

Revision ID: location_rich_fields
Revises: asset_rich_fields
Create Date: 2026-06-06

手工撰写（MySQL 生产 + SQLite 开发/测试）。
tb_location 加 1 个可空标量列（batch_alter_table，SQLite 表重建安全）：
  image_url(主图)。
位置↔供应商/客户的 M:N 关联表（tb_vendor_location/tb_customer_location）
已由既有迁移建好（vendor/customer 侧维护 location_ids），本迁移不涉及。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "location_rich_fields"
down_revision: str | Sequence[str] | None = "asset_rich_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tb_location") as batch_op:
        batch_op.add_column(sa.Column("image_url", sa.String(length=512), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("tb_location") as batch_op:
        batch_op.drop_column("image_url")
