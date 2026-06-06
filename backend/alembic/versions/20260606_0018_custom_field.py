"""custom field def table + 5 host custom_values columns

Revision ID: custom_field
Revises: push_switch_verify
Create Date: 2026-06-06

手工撰写（MySQL 生产 + SQLite 开发/测试）。
- 新建 tb_custom_field_def（UUID+Timestamp+SoftDelete+Tenant，多态 entity_type，
  唯一 (company_id, entity_type, key)）；
- 给 5 张业务宿主表 batch_alter_table 加 custom_values JSON 列（默认 '{}' 走括号
  表达式默认，避开 MySQL JSON 字面默认 1101）。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.models.base import DATETIME6

revision: str = "custom_field"
down_revision: str | Sequence[str] | None = "push_switch_verify"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_HOSTS = ("tb_work_order", "tb_asset", "tb_request", "tb_location", "tb_part")


def upgrade() -> None:
    op.create_table(
        "tb_custom_field_def",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(length=36),
            sa.ForeignKey("tb_company.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("field_type", sa.String(length=20), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=sa.text("('')")),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("default_value", sa.JSON(), nullable=True),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column("validation_rules", sa.JSON(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("deleted_at", DATETIME6, nullable=True),
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
        sa.UniqueConstraint(
            "company_id", "entity_type", "key", name="uq_custom_field_def_company_entity_key"
        ),
    )
    op.create_index(
        "ix_tb_custom_field_def_company_id", "tb_custom_field_def", ["company_id"]
    )
    op.create_index(
        "ix_tb_custom_field_def_entity_type", "tb_custom_field_def", ["entity_type"]
    )
    op.create_index(
        "ix_tb_custom_field_def_is_active", "tb_custom_field_def", ["is_active"]
    )
    op.create_index(
        "ix_tb_custom_field_def_created_at", "tb_custom_field_def", ["created_at"]
    )

    for tbl in _HOSTS:
        with op.batch_alter_table(tbl) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "custom_values",
                    sa.JSON(),
                    nullable=False,
                    server_default=sa.text("('{}')"),
                )
            )


def downgrade() -> None:
    for tbl in _HOSTS:
        with op.batch_alter_table(tbl) as batch_op:
            batch_op.drop_column("custom_values")
    # MySQL DROP TABLE 连带删索引与 FK；仅 SQLite 显式删索引（保持既有验证行为）。
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("ix_tb_custom_field_def_created_at", table_name="tb_custom_field_def")
        op.drop_index("ix_tb_custom_field_def_is_active", table_name="tb_custom_field_def")
        op.drop_index("ix_tb_custom_field_def_entity_type", table_name="tb_custom_field_def")
        op.drop_index("ix_tb_custom_field_def_company_id", table_name="tb_custom_field_def")
    op.drop_table("tb_custom_field_def")
