"""SOP 多租户硬化：删 NULL-company 行 + 4 处 per-company 复合唯一 + 17 表 NOT NULL

Revision ID: sop_tenancy_hardening
Revises: p6_commercialization_gating
Create Date: 2026-06-04

把 SOP 多租户从应用层硬化到 schema 层：
1. 删存量 NULL-company SOP 行（按 FK 依赖自底向上；假定无真实 prod 数据）。
2. 4 处全局唯一自然键改 (company_id, …) 复合唯一：
   - tb_procedure_field(company_id, key)
   - tb_procedure_source_docx(company_id, procedure_group_id)
   - tb_procedure_asset(company_id, sha256)
   - tb_procedure_asset_reference(company_id, asset_id, procedure_id)
3. 17 个 SOP 租户表 company_id 收 NOT NULL（fail-closed）。

方言策略：用 batch_alter_table 默认 recreate="auto" —— MySQL 走 in-place ALTER（保留
tb_procedure/tb_folder 的 MySQL-only 生成列 current_guard/draft_guard/active_code_version/
active_unique_key 及其 UNIQUE，不重建表），SQLite 在需要时（改唯一约束 / 改列 nullability）
自动重建表（SQLite 上这些生成列不存在，重建安全）。

downgrade 反向放回 nullable / 全局唯一；删除的 NULL 行不可逆（文档已注明）。
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "sop_tenancy_hardening"
down_revision: str | Sequence[str] | None = "p6_commercialization_gating"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CID = sa.String(length=36)

# NOT NULL 收紧的全部 17 个 SOP 租户表（child→parent 顺序也用于删 NULL 行）。
_TENANT_TABLES: tuple[str, ...] = (
    "tb_procedure_asset_reference",
    "tb_procedure_node",
    "tb_attachment",
    "tb_procedure_audit_log",
    "tb_folder_audit_log",
    "tb_heading_learning_event",
    "tb_batch_import_item",
    "tb_procedure_asset",
    "tb_procedure",
    "tb_folder_sequence",
    "tb_batch_import_job",
    "tb_folder",
    "tb_procedure_field",
    "tb_procedure_settings",
    "tb_procedure_source_docx",
    "tb_heading_style_rule",
    "tb_numbering_profile",
)


def upgrade() -> None:
    # 1) 删存量 NULL-company 行（child→parent，避免 FK RESTRICT 干扰）。
    for table in _TENANT_TABLES:
        op.execute(f"DELETE FROM {table} WHERE company_id IS NULL")

    # 2) 4 处全局唯一 → per-company 复合唯一（顺带这 4 表收 NOT NULL）。
    with op.batch_alter_table("tb_procedure_field") as b:
        b.drop_constraint("uq_tb_procedure_field_key", type_="unique")
        b.create_unique_constraint(
            "uq_tb_procedure_field_company_key", ["company_id", "key"]
        )
        b.alter_column("company_id", existing_type=_CID, nullable=False)

    with op.batch_alter_table("tb_procedure_asset") as b:
        b.drop_constraint("uq_tb_procedure_asset_sha256", type_="unique")
        b.create_unique_constraint(
            "uq_tb_procedure_asset_company_sha256", ["company_id", "sha256"]
        )
        b.alter_column("company_id", existing_type=_CID, nullable=False)

    with op.batch_alter_table("tb_procedure_source_docx") as b:
        b.drop_index("uq_tb_procedure_source_docx_procedure_group_id")
        b.create_unique_constraint(
            "uq_tb_procedure_source_docx_company_procedure_group",
            ["company_id", "procedure_group_id"],
        )
        b.alter_column("company_id", existing_type=_CID, nullable=False)

    with op.batch_alter_table("tb_procedure_asset_reference") as b:
        b.drop_index("uq_tb_procedure_asset_reference_asset_id_procedure_id")
        b.create_index(
            "uq_tb_procedure_asset_reference_company_asset_procedure",
            ["company_id", "asset_id", "procedure_id"],
            unique=True,
        )
        b.alter_column("company_id", existing_type=_CID, nullable=False)

    # 3) 其余 13 表仅收 NOT NULL。
    _unique_handled = {
        "tb_procedure_field",
        "tb_procedure_asset",
        "tb_procedure_source_docx",
        "tb_procedure_asset_reference",
    }
    for table in _TENANT_TABLES:
        if table in _unique_handled:
            continue
        with op.batch_alter_table(table) as b:
            b.alter_column("company_id", existing_type=_CID, nullable=False)


def downgrade() -> None:
    # 注意：upgrade 删除的 NULL-company 行不可逆，此处仅还原约束/可空性。
    _unique_handled = {
        "tb_procedure_field",
        "tb_procedure_asset",
        "tb_procedure_source_docx",
        "tb_procedure_asset_reference",
    }
    for table in _TENANT_TABLES:
        if table in _unique_handled:
            continue
        with op.batch_alter_table(table) as b:
            b.alter_column("company_id", existing_type=_CID, nullable=True)

    with op.batch_alter_table("tb_procedure_asset_reference") as b:
        b.alter_column("company_id", existing_type=_CID, nullable=True)
        b.drop_index("uq_tb_procedure_asset_reference_company_asset_procedure")
        b.create_index(
            "uq_tb_procedure_asset_reference_asset_id_procedure_id",
            ["asset_id", "procedure_id"],
            unique=True,
        )

    with op.batch_alter_table("tb_procedure_source_docx") as b:
        b.alter_column("company_id", existing_type=_CID, nullable=True)
        b.drop_constraint(
            "uq_tb_procedure_source_docx_company_procedure_group", type_="unique"
        )
        b.create_index(
            "uq_tb_procedure_source_docx_procedure_group_id",
            ["procedure_group_id"],
            unique=True,
        )

    with op.batch_alter_table("tb_procedure_asset") as b:
        b.alter_column("company_id", existing_type=_CID, nullable=True)
        b.drop_constraint("uq_tb_procedure_asset_company_sha256", type_="unique")
        b.create_unique_constraint("uq_tb_procedure_asset_sha256", ["sha256"])

    with op.batch_alter_table("tb_procedure_field") as b:
        b.alter_column("company_id", existing_type=_CID, nullable=True)
        b.drop_constraint("uq_tb_procedure_field_company_key", type_="unique")
        b.create_unique_constraint("uq_tb_procedure_field_key", ["key"])
