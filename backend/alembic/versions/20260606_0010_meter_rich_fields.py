"""meter rich fields: tb_meter 加 image_url + tb_meter_user

Revision ID: meter_rich_fields
Revises: location_rich_fields
Create Date: 2026-06-06

手工撰写（MySQL 生产 + SQLite 开发/测试）。
- tb_meter 加 1 个可空标量列（batch_alter_table，SQLite 表重建安全）：image_url(主图)。
- 新建 tb_meter_user（UUID+Timestamp+Tenant）：计量↔用户 M:N（该计量的通知关注人）。
  唯一 (meter_id,user_id)；company_id/meter_id/user_id 均带 FK CASCADE 与索引。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.models.base import DATETIME6

revision: str = "meter_rich_fields"
down_revision: str | Sequence[str] | None = "location_rich_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tb_meter") as batch_op:
        batch_op.add_column(sa.Column("image_url", sa.String(length=512), nullable=True))

    op.create_table(
        "tb_meter_user",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(length=36),
            sa.ForeignKey("tb_company.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "meter_id",
            sa.String(length=36),
            sa.ForeignKey("tb_meter.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("tb_user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
        sa.UniqueConstraint("meter_id", "user_id", name="uq_meter_user"),
    )
    op.create_index("ix_tb_meter_user_company_id", "tb_meter_user", ["company_id"])
    op.create_index("ix_tb_meter_user_meter_id", "tb_meter_user", ["meter_id"])
    op.create_index("ix_tb_meter_user_user_id", "tb_meter_user", ["user_id"])


def downgrade() -> None:
    # MySQL 拒绝先删被 FK 占用的索引（1553）；DROP TABLE 连带删索引与 FK，故仅 SQLite
    # 显式删索引（保持其既有验证行为），MySQL 直接 DROP TABLE。
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("ix_tb_meter_user_user_id", table_name="tb_meter_user")
        op.drop_index("ix_tb_meter_user_meter_id", table_name="tb_meter_user")
        op.drop_index("ix_tb_meter_user_company_id", table_name="tb_meter_user")
    op.drop_table("tb_meter_user")

    with op.batch_alter_table("tb_meter") as batch_op:
        batch_op.drop_column("image_url")
