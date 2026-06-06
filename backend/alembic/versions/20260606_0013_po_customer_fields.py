"""po/customer fields: tb_purchase_order 收货细化 + tb_customer 账单字段

Revision ID: po_customer_fields
Revises: pm_scheduling_fields
Create Date: 2026-06-06

手工撰写（MySQL 生产 + SQLite 开发/测试）。
tb_purchase_order 加 8 个可空 String 列（收货信息细化；保留既有
shipping_address/shipping_method/terms_of_payment/expected_delivery_date）：
  shipping_to_name / shipping_company_name / shipping_city / shipping_state /
  shipping_zip_code / shipping_phone / shipping_fax / requisitioned_by_name
tb_customer 加 3 个可空 String 列（账单信息细化；与既有 billing_currency 同组）：
  billing_name / billing_address / billing_address2
全可空、无 server_default（String 列，按既有 String 列迁移惯例）。
batch_alter_table 保证 SQLite 表重建安全。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "po_customer_fields"
down_revision: str | Sequence[str] | None = "pm_scheduling_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tb_purchase_order") as batch_op:
        batch_op.add_column(sa.Column("shipping_to_name", sa.String(length=200), nullable=True))
        batch_op.add_column(
            sa.Column("shipping_company_name", sa.String(length=300), nullable=True)
        )
        batch_op.add_column(sa.Column("shipping_city", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("shipping_state", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("shipping_zip_code", sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column("shipping_phone", sa.String(length=60), nullable=True))
        batch_op.add_column(sa.Column("shipping_fax", sa.String(length=60), nullable=True))
        batch_op.add_column(
            sa.Column("requisitioned_by_name", sa.String(length=200), nullable=True)
        )

    with op.batch_alter_table("tb_customer") as batch_op:
        batch_op.add_column(sa.Column("billing_name", sa.String(length=300), nullable=True))
        batch_op.add_column(sa.Column("billing_address", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("billing_address2", sa.String(length=500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("tb_customer") as batch_op:
        batch_op.drop_column("billing_address2")
        batch_op.drop_column("billing_address")
        batch_op.drop_column("billing_name")

    with op.batch_alter_table("tb_purchase_order") as batch_op:
        batch_op.drop_column("requisitioned_by_name")
        batch_op.drop_column("shipping_fax")
        batch_op.drop_column("shipping_phone")
        batch_op.drop_column("shipping_zip_code")
        batch_op.drop_column("shipping_state")
        batch_op.drop_column("shipping_city")
        batch_op.drop_column("shipping_company_name")
        batch_op.drop_column("shipping_to_name")
