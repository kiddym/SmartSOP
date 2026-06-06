"""form field config table

Revision ID: form_field_config
Revises: company_profile_prefs
Create Date: 2026-06-06

手工撰写（MySQL 生产 + SQLite 开发/测试）。
新建 tb_form_field_config（UUID+Timestamp+Tenant），per company×form×field
控制显隐/必填，唯一约束 (company_id, form_key, field_name)。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.models.base import DATETIME6

revision: str = "form_field_config"
down_revision: str | Sequence[str] | None = "company_profile_prefs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tb_form_field_config",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(length=36),
            sa.ForeignKey("tb_company.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("form_key", sa.String(length=32), nullable=False),
        sa.Column("field_name", sa.String(length=64), nullable=False),
        sa.Column("visible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
        sa.UniqueConstraint(
            "company_id", "form_key", "field_name", name="uq_form_field_config"
        ),
    )
    op.create_index(
        "ix_tb_form_field_config_company_id", "tb_form_field_config", ["company_id"]
    )
    op.create_index(
        "ix_tb_form_field_config_form_key", "tb_form_field_config", ["form_key"]
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("ix_tb_form_field_config_form_key", table_name="tb_form_field_config")
        op.drop_index("ix_tb_form_field_config_company_id", table_name="tb_form_field_config")
    op.drop_table("tb_form_field_config")
