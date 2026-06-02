"""universal attachment: generalize tb_procedure_attachment -> tb_attachment

Revision ID: universal_attachment
Revises: platform_account_config
Create Date: 2026-06-02

Hand-authored (MySQL prod + SQLite dev/test). In-place generalization of the
procedure-only attachment table into a polymorphic attachment table:

- create the new ``tb_attachment`` (DDL == ``Attachment`` model: polymorphic
  ``entity_type`` / ``entity_id`` soft association, no ``tb_procedure`` FK, but
  retains the ``NullableTenantMixin`` ``company_id`` FK to ``tb_company``);
- migrate existing rows losslessly via ``INSERT ... SELECT`` with
  ``entity_type = 'procedure'`` and ``entity_id = procedure_id``;
- drop the legacy ``tb_procedure_attachment``.

Downgrade rebuilds the legacy table (procedure_id NOT NULL + RESTRICT FK to
tb_procedure + the original five indexes) and back-fills only the
``entity_type = 'procedure'`` rows; rows belonging to other entity types are
discarded (rolling back to a world without universal attachments).

注：MySQL 全链 alembic 重放受既有 initial_schema 的 TEXT server_default 问题阻塞
（与本迁移无关）；本迁移 DDL+INSERT 已在 MySQL 9.x 上以最小 fixture 双向验证，
生产 MySQL 全链重放待按实际版本手验。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.models.base import DATETIME6

revision: str = "universal_attachment"
down_revision: str | Sequence[str] | None = "platform_account_config"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- new polymorphic tb_attachment (== Attachment model) ------------------
    op.create_table(
        "tb_attachment",
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", DATETIME6, nullable=True),
        sa.Column("company_id", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["tb_company.id"],
            name=op.f("fk_tb_attachment_company_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tb_attachment")),
    )
    op.create_index(
        op.f("ix_tb_attachment_company_id"), "tb_attachment", ["company_id"], unique=False
    )
    op.create_index(
        op.f("ix_tb_attachment_created_at"), "tb_attachment", ["created_at"], unique=False
    )
    op.create_index(
        "ix_tb_attachment_entity",
        "tb_attachment",
        ["entity_type", "entity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tb_attachment_is_active"), "tb_attachment", ["is_active"], unique=False
    )
    op.create_index(
        "ix_tb_attachment_storage_path", "tb_attachment", ["storage_path"], unique=False
    )

    # --- lossless data migration: every legacy row is a 'procedure' attachment -
    op.execute(
        "INSERT INTO tb_attachment "
        "(id, entity_type, entity_id, file_name, storage_path, mime_type, "
        " size_bytes, description, sort_order, company_id, created_at, "
        " updated_at, is_active, deleted_at) "
        "SELECT id, 'procedure', procedure_id, file_name, storage_path, "
        " mime_type, size_bytes, description, sort_order, company_id, "
        " created_at, updated_at, is_active, deleted_at "
        "FROM tb_procedure_attachment"
    )

    # --- drop the legacy procedure-only table ---------------------------------
    op.drop_index(
        "ix_tb_procedure_attachment_company_id",
        table_name="tb_procedure_attachment",
    )
    op.drop_index(
        op.f("ix_tb_procedure_attachment_created_at"),
        table_name="tb_procedure_attachment",
    )
    op.drop_index(
        op.f("ix_tb_procedure_attachment_is_active"),
        table_name="tb_procedure_attachment",
    )
    op.drop_index(
        "ix_tb_procedure_attachment_procedure_id",
        table_name="tb_procedure_attachment",
    )
    op.drop_index(
        "ix_tb_procedure_attachment_storage_path",
        table_name="tb_procedure_attachment",
    )
    op.drop_table("tb_procedure_attachment")


def downgrade() -> None:
    # --- rebuild the legacy procedure-only tb_procedure_attachment ------------
    op.create_table(
        "tb_procedure_attachment",
        sa.Column("procedure_id", sa.String(length=36), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", DATETIME6, nullable=True),
        sa.Column("company_id", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(
            ["procedure_id"],
            ["tb_procedure.id"],
            name=op.f("fk_tb_procedure_attachment_procedure_id"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tb_procedure_attachment")),
    )
    op.create_index(
        "ix_tb_procedure_attachment_company_id",
        "tb_procedure_attachment",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tb_procedure_attachment_created_at"),
        "tb_procedure_attachment",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tb_procedure_attachment_is_active"),
        "tb_procedure_attachment",
        ["is_active"],
        unique=False,
    )
    op.create_index(
        "ix_tb_procedure_attachment_procedure_id",
        "tb_procedure_attachment",
        ["procedure_id"],
        unique=False,
    )
    op.create_index(
        "ix_tb_procedure_attachment_storage_path",
        "tb_procedure_attachment",
        ["storage_path"],
        unique=False,
    )

    # --- restore the company_id FK that phase0_platform added (MySQL only) -----
    # phase0 added company_id via add_column with an inline sa.ForeignKey on
    # non-SQLite dialects only (see phase0_platform lines 118-133). We mirror
    # that here so MySQL up→down leaves tb_procedure_attachment in the same FK
    # state as before the upgrade. SQLite never had this FK, so we skip it.
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key(
            op.f("fk_tb_procedure_attachment_company_id"),
            "tb_procedure_attachment",
            "tb_company",
            ["company_id"],
            ["id"],
            ondelete="CASCADE",
        )

    # --- back-fill only the 'procedure' rows; other entity types are dropped --
    op.execute(
        "INSERT INTO tb_procedure_attachment "
        "(id, procedure_id, file_name, storage_path, mime_type, size_bytes, "
        " description, sort_order, company_id, created_at, updated_at, "
        " is_active, deleted_at) "
        "SELECT id, entity_id, file_name, storage_path, mime_type, size_bytes, "
        " description, sort_order, company_id, created_at, updated_at, "
        " is_active, deleted_at "
        "FROM tb_attachment WHERE entity_type = 'procedure'"
    )

    op.drop_index("ix_tb_attachment_storage_path", table_name="tb_attachment")
    op.drop_index(op.f("ix_tb_attachment_is_active"), table_name="tb_attachment")
    op.drop_index("ix_tb_attachment_entity", table_name="tb_attachment")
    op.drop_index(op.f("ix_tb_attachment_created_at"), table_name="tb_attachment")
    op.drop_index(op.f("ix_tb_attachment_company_id"), table_name="tb_attachment")
    op.drop_table("tb_attachment")
