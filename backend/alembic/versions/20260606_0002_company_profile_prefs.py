"""company profile + general preferences

Revision ID: company_profile_prefs
Revises: user_profile_fields
Create Date: 2026-06-06

手工撰写（MySQL 生产 + SQLite 开发/测试）。
- tb_company 加 9 个可空 profile 列（address/city/state/zip_code/phone/
  email/website/employees_count/logo_url）。
- tb_company_settings 加 9 个 general-preferences 列（带 server_default，
  既有行回填合理默认）。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "company_profile_prefs"
down_revision: str | Sequence[str] | None = "user_profile_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tb_company") as batch_op:
        batch_op.add_column(sa.Column("address", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("city", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("state", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("zip_code", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("phone", sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column("email", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("website", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("employees_count", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("logo_url", sa.String(length=512), nullable=True))

    with op.batch_alter_table("tb_company_settings") as batch_op:
        batch_op.add_column(
            sa.Column(
                "language", sa.String(length=16), server_default="zh-CN", nullable=False
            )
        )
        batch_op.add_column(sa.Column("business_type", sa.String(length=64), nullable=True))
        batch_op.add_column(
            sa.Column(
                "wo_update_for_requesters", sa.Boolean(), server_default="0", nullable=False
            )
        )
        batch_op.add_column(
            sa.Column(
                "disable_closed_wo_notification",
                sa.Boolean(),
                server_default="0",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "ask_feedback_on_wo_closed", sa.Boolean(), server_default="0", nullable=False
            )
        )
        batch_op.add_column(
            sa.Column(
                "labor_cost_in_total_cost", sa.Boolean(), server_default="1", nullable=False
            )
        )
        batch_op.add_column(
            sa.Column("simplified_work_order", sa.Boolean(), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column(
                "days_before_pm_notification", sa.Integer(), server_default="0", nullable=False
            )
        )
        batch_op.add_column(
            sa.Column("auto_assign_requests", sa.Boolean(), server_default="0", nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table("tb_company_settings") as batch_op:
        batch_op.drop_column("auto_assign_requests")
        batch_op.drop_column("days_before_pm_notification")
        batch_op.drop_column("simplified_work_order")
        batch_op.drop_column("labor_cost_in_total_cost")
        batch_op.drop_column("ask_feedback_on_wo_closed")
        batch_op.drop_column("disable_closed_wo_notification")
        batch_op.drop_column("wo_update_for_requesters")
        batch_op.drop_column("business_type")
        batch_op.drop_column("language")

    with op.batch_alter_table("tb_company") as batch_op:
        batch_op.drop_column("logo_url")
        batch_op.drop_column("employees_count")
        batch_op.drop_column("website")
        batch_op.drop_column("email")
        batch_op.drop_column("phone")
        batch_op.drop_column("zip_code")
        batch_op.drop_column("state")
        batch_op.drop_column("city")
        batch_op.drop_column("address")
