"""asset rich fields: tb_asset 加 area/additional_infos/image_url

Revision ID: asset_rich_fields
Revises: floor_plan
Create Date: 2026-06-06

手工撰写（MySQL 生产 + SQLite 开发/测试）。
tb_asset 加 3 个可空标量列（batch_alter_table，SQLite 表重建安全）：
  area(区域/库区) / additional_infos(更多信息) / image_url(主图)。
资产↔供应商/客户/备件的 M:N 关联表（tb_vendor_asset/tb_customer_asset/
tb_part_asset）已由既有迁移建好，本迁移不涉及。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "asset_rich_fields"
down_revision: str | Sequence[str] | None = "floor_plan"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tb_asset") as batch_op:
        batch_op.add_column(sa.Column("area", sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column("additional_infos", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("image_url", sa.String(length=512), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("tb_asset") as batch_op:
        batch_op.drop_column("image_url")
        batch_op.drop_column("additional_infos")
        batch_op.drop_column("area")
