"""phase0 platform: company/role/user tables + SOP company_id

Revision ID: phase0_platform
Revises: drop_legacy_chapter_step
Create Date: 2026-05-30

Hand-authored (MySQL prod + SQLite dev/test). Creates the multi-tenant
platform tables (tb_company / tb_role / tb_user) and adds a NULLABLE
``company_id`` to every existing SOP business table as the Phase 0 -> Phase 1
tenant bridge (NOT NULL tightening + enforcement happen in Phase 1).
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import DATETIME6

revision: str = "phase0_platform"
down_revision: str | Sequence[str] | None = "drop_legacy_chapter_step"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# SOP business tables that gain a nullable company_id (one per
# NullableTenantMixin model; see app/models/*.py).
_SOP_TABLES: tuple[str, ...] = (
    "tb_folder",
    "tb_folder_sequence",
    "tb_folder_audit_log",
    "tb_procedure",
    "tb_procedure_node",
    "tb_procedure_field",
    "tb_procedure_settings",
    "tb_procedure_source_docx",
    "tb_procedure_attachment",
    "tb_procedure_asset",
    "tb_procedure_asset_reference",
    "tb_procedure_audit_log",
)


def upgrade() -> None:
    op.create_table(
        "tb_company",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column(
            "status",
            sa.Enum("active", "suspended", name="companystatus"),
            nullable=False,
        ),
        sa.Column("locale", sa.String(16), nullable=False),
        sa.Column("is_platform_admin_org", sa.Boolean(), nullable=False),
        sa.Column("plan", sa.String(32), nullable=True),
        sa.Column("subscription_status", sa.String(32), nullable=True),
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
    )
    op.create_index("ix_tb_company_slug", "tb_company", ["slug"], unique=True)

    op.create_table(
        "tb_role",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("tb_company.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("is_builtin", sa.Boolean(), nullable=False),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
        sa.UniqueConstraint("company_id", "code", name="uq_role_company_code"),
    )
    op.create_index("ix_tb_role_company_id", "tb_role", ["company_id"])

    op.create_table(
        "tb_user",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("tb_company.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column(
            "status",
            sa.Enum("active", "disabled", name="userstatus"),
            nullable=False,
        ),
        sa.Column(
            "role_id",
            sa.String(36),
            sa.ForeignKey("tb_role.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("locale", sa.String(16), nullable=False),
        sa.Column("last_login_at", DATETIME6, nullable=True),
        sa.Column("is_platform_admin", sa.Boolean(), nullable=False),
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
        sa.UniqueConstraint("company_id", "email", name="uq_user_company_email"),
    )
    op.create_index("ix_tb_user_company_id", "tb_user", ["company_id"])
    op.create_index("ix_tb_user_email", "tb_user", ["email"])

    for table in _SOP_TABLES:
        op.add_column(
            table,
            sa.Column(
                "company_id",
                sa.String(36),
                sa.ForeignKey("tb_company.id", ondelete="CASCADE"),
                nullable=True,
            ),
        )
        op.create_index(f"ix_{table}_company_id", table, ["company_id"])


def downgrade() -> None:
    for table in _SOP_TABLES:
        op.drop_index(f"ix_{table}_company_id", table_name=table)
        op.drop_column(table, "company_id")

    op.drop_index("ix_tb_user_email", table_name="tb_user")
    op.drop_index("ix_tb_user_company_id", table_name="tb_user")
    op.drop_table("tb_user")

    op.drop_index("ix_tb_role_company_id", table_name="tb_role")
    op.drop_table("tb_role")

    op.drop_index("ix_tb_company_slug", table_name="tb_company")
    op.drop_table("tb_company")
