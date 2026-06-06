"""user profile fields: tb_user 加 phone/job_title/rate/avatar_url

Revision ID: user_profile_fields
Revises: p6_stripe_billing
Create Date: 2026-06-06

手工撰写（MySQL 生产 + SQLite 开发/测试）。
tb_user 加 4 个可空 profile 列（batch_alter_table，SQLite 表重建安全）：
  phone / job_title / rate(Numeric 18,4，工时默认费率) / avatar_url。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "user_profile_fields"
down_revision: str | Sequence[str] | None = "p6_stripe_billing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tb_user") as batch_op:
        batch_op.add_column(sa.Column("phone", sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column("job_title", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("rate", sa.Numeric(18, 4), nullable=True))
        batch_op.add_column(sa.Column("avatar_url", sa.String(length=512), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("tb_user") as batch_op:
        batch_op.drop_column("avatar_url")
        batch_op.drop_column("rate")
        batch_op.drop_column("job_title")
        batch_op.drop_column("phone")
