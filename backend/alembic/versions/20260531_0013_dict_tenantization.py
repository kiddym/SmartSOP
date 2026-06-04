"""dict 三表租户化：+company_id + 复合唯一（SQLite batch 重建）

Revision ID: dict_tenantization
Revises: numbering_profile
Create Date: 2026-05-31

三表加 company_id（nullable，对齐 NullableTenantMixin）+ 复合唯一约束。
recreate 模式按方言区分（见 _recreate_mode）：SQLite 改唯一约束须整表重建
(recreate="always")；MySQL 走 recreate="auto" 的 in-place ALTER——强制 "always"
会让 MySQL 反射重建时把命名唯一约束识别为 index，drop_constraint 按名找不到而报
"No such constraint"。约束名须与 P1b(uq_heading_style_rule_style_name)/
P1d(uq_numbering_profile_pattern_key) 一致。
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "dict_tenantization"
down_revision: str | Sequence[str] | None = "numbering_profile"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _recreate_mode() -> str:
    # SQLite 不支持 in-place 改唯一约束/加 FK，须整表重建；MySQL/其它支持 in-place
    # ALTER（drop_constraint 按名直发 DDL，无须反射，避免命名唯一约束被误判为 index）。
    return "always" if op.get_bind().dialect.name == "sqlite" else "auto"


def _add_company(
    table: str,
    *,
    old_unique: str | None,
    new_unique: tuple[str, str] | None,
    new_uq_name: str | None,
) -> None:
    with op.batch_alter_table(table, recreate=_recreate_mode()) as b:
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
    with op.batch_alter_table("tb_heading_learning_event", recreate=_recreate_mode()) as b:
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
    # SQLite 走整表重建（recreate="always"）：batch 内 drop_index/drop_column 驱动重建。
    # MySQL 走 in-place ALTER：company_id 的索引被 company FK 占用，须先删 FK（1553），
    # 否则其后的 drop_index/drop_column 无法执行。先删含 company_id 的索引（否则 SQLite
    # batch 重建表时会照搬引用已删列的索引而报错）。
    is_mysql = op.get_bind().dialect.name != "sqlite"
    if is_mysql:
        op.drop_constraint(
            "fk_tb_heading_learning_event_company",
            "tb_heading_learning_event",
            type_="foreignkey",
        )
    with op.batch_alter_table("tb_heading_learning_event", recreate=_recreate_mode()) as b:
        b.drop_index("ix_tb_heading_learning_event_company_style_proc")
        b.drop_column("company_id")
    if is_mysql:
        op.drop_constraint(
            "fk_tb_numbering_profile_company", "tb_numbering_profile", type_="foreignkey"
        )
    with op.batch_alter_table("tb_numbering_profile", recreate=_recreate_mode()) as b:
        b.drop_index("ix_tb_numbering_profile_company_id")
        b.drop_constraint("uq_numbering_profile_company_pattern", type_="unique")
        b.create_unique_constraint("uq_numbering_profile_pattern_key", ["pattern_key"])
        b.drop_column("company_id")
    if is_mysql:
        op.drop_constraint(
            "fk_tb_heading_style_rule_company", "tb_heading_style_rule", type_="foreignkey"
        )
    with op.batch_alter_table("tb_heading_style_rule", recreate=_recreate_mode()) as b:
        b.drop_index("ix_tb_heading_style_rule_company_id")
        b.drop_constraint("uq_heading_style_rule_company_style", type_="unique")
        b.create_unique_constraint("uq_heading_style_rule_style_name", ["style_name"])
        b.drop_column("company_id")
