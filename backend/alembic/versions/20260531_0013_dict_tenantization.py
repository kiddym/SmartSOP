"""dict 三表租户化：+company_id + 复合唯一（SQLite batch 重建）

Revision ID: dict_tenantization
Revises: numbering_profile
Create Date: 2026-05-31

三表加 company_id（nullable，对齐 NullableTenantMixin）+ 复合唯一约束。
SQLite 改唯一约束须 batch_alter_table(recreate="always") 重建表；MySQL 亦兼容。
约束名须与 P1b(uq_heading_style_rule_style_name)/P1d(uq_numbering_profile_pattern_key) 一致。
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "dict_tenantization"
down_revision: str | Sequence[str] | None = "numbering_profile"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _add_company(
    table: str,
    *,
    old_unique: str | None,
    new_unique: tuple[str, str] | None,
    new_uq_name: str | None,
) -> None:
    with op.batch_alter_table(table, recreate="always") as b:
        b.add_column(sa.Column("company_id", sa.String(length=36), nullable=True))
        b.create_index(f"ix_{table}_company_id", ["company_id"])
        if old_unique:
            b.drop_constraint(old_unique, type_="unique")
        if new_unique and new_uq_name:
            b.create_unique_constraint(new_uq_name, list(new_unique))
        b.create_foreign_key(
            f"fk_{table}_company", "tb_company", ["company_id"], ["id"], ondelete="CASCADE"
        )


def upgrade() -> None:
    _add_company(
        "tb_heading_style_rule",
        old_unique="uq_heading_style_rule_style_name",
        new_unique=("company_id", "style_name"),
        new_uq_name="uq_heading_style_rule_company_style",
    )
    _add_company(
        "tb_numbering_profile",
        old_unique="uq_numbering_profile_pattern_key",
        new_unique=("company_id", "pattern_key"),
        new_uq_name="uq_numbering_profile_company_pattern",
    )
    # 事件表无唯一约束，仅加列 + 复合索引
    with op.batch_alter_table("tb_heading_learning_event", recreate="always") as b:
        b.add_column(sa.Column("company_id", sa.String(length=36), nullable=True))
        b.create_index(
            "ix_tb_heading_learning_event_company_style_proc",
            ["company_id", "style_name", "procedure_id"],
        )
        b.create_foreign_key(
            "fk_tb_heading_learning_event_company",
            "tb_company",
            ["company_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    # 先删含 company_id 的索引（否则 batch 重建表时会照搬引用已删列的索引而报错）。
    with op.batch_alter_table("tb_heading_learning_event", recreate="always") as b:
        b.drop_index("ix_tb_heading_learning_event_company_style_proc")
        b.drop_column("company_id")
    with op.batch_alter_table("tb_numbering_profile", recreate="always") as b:
        b.drop_index("ix_tb_numbering_profile_company_id")
        b.drop_constraint("uq_numbering_profile_company_pattern", type_="unique")
        b.create_unique_constraint("uq_numbering_profile_pattern_key", ["pattern_key"])
        b.drop_column("company_id")
    with op.batch_alter_table("tb_heading_style_rule", recreate="always") as b:
        b.drop_index("ix_tb_heading_style_rule_company_id")
        b.drop_constraint("uq_heading_style_rule_company_style", type_="unique")
        b.create_unique_constraint("uq_heading_style_rule_style_name", ["style_name"])
        b.drop_column("company_id")
