"""add tb_batch_import_job / tb_batch_import_item (batch word parsing — backend foundation)"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.models.base import DATETIME6

revision: str = "add_batch_import"
down_revision: str | Sequence[str] | None = "phase5b_email_storage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tb_batch_import_job",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=True),
        sa.Column("folder_id", sa.String(length=36), nullable=False),
        sa.Column("parse_mode", sa.String(length=20), nullable=False, server_default="smart"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="parsing"),
        sa.Column("counts", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("expires_at", DATETIME6, nullable=True),
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", DATETIME6, nullable=True),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["tb_company.id"],
            name="fk_tb_batch_import_job_company_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["folder_id"],
            ["tb_folder.id"],
            name="fk_tb_batch_import_job_folder_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["tb_user.id"],
            name="fk_tb_batch_import_job_created_by",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tb_batch_import_job"),
    )
    op.create_index("ix_tb_batch_import_job_company_id", "tb_batch_import_job", ["company_id"])
    op.create_index("ix_tb_batch_import_job_folder_id", "tb_batch_import_job", ["folder_id"])
    op.create_index("ix_tb_batch_import_job_status", "tb_batch_import_job", ["status"])
    op.create_index("ix_tb_batch_import_job_is_active", "tb_batch_import_job", ["is_active"])
    op.create_index("ix_tb_batch_import_job_created_at", "tb_batch_import_job", ["created_at"])

    op.create_table(
        "tb_batch_import_item",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=True),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("parse_blob_ref", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("docx_ref", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("review_revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_procedure_id", sa.String(length=36), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("leased_until", DATETIME6, nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.String(length=36), nullable=True),
        sa.Column("reviewed_at", DATETIME6, nullable=True),
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", DATETIME6, nullable=True),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["tb_company.id"],
            name="fk_tb_batch_import_item_company_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["tb_batch_import_job.id"],
            name="fk_tb_batch_import_item_job_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_procedure_id"],
            ["tb_procedure.id"],
            name="fk_tb_batch_import_item_created_procedure_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tb_batch_import_item"),
    )
    op.create_index("ix_tb_batch_import_item_company_id", "tb_batch_import_item", ["company_id"])
    op.create_index("ix_tb_batch_import_item_job_id", "tb_batch_import_item", ["job_id"])
    op.create_index(
        "ix_tb_batch_import_item_content_hash", "tb_batch_import_item", ["content_hash"]
    )
    op.create_index("ix_tb_batch_import_item_status", "tb_batch_import_item", ["status"])
    op.create_index("ix_tb_batch_import_item_is_active", "tb_batch_import_item", ["is_active"])
    op.create_index("ix_tb_batch_import_item_created_at", "tb_batch_import_item", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_tb_batch_import_item_created_at", table_name="tb_batch_import_item")
    op.drop_index("ix_tb_batch_import_item_is_active", table_name="tb_batch_import_item")
    op.drop_index("ix_tb_batch_import_item_status", table_name="tb_batch_import_item")
    op.drop_index("ix_tb_batch_import_item_content_hash", table_name="tb_batch_import_item")
    op.drop_index("ix_tb_batch_import_item_job_id", table_name="tb_batch_import_item")
    op.drop_index("ix_tb_batch_import_item_company_id", table_name="tb_batch_import_item")
    op.drop_table("tb_batch_import_item")

    op.drop_index("ix_tb_batch_import_job_created_at", table_name="tb_batch_import_job")
    op.drop_index("ix_tb_batch_import_job_is_active", table_name="tb_batch_import_job")
    op.drop_index("ix_tb_batch_import_job_status", table_name="tb_batch_import_job")
    op.drop_index("ix_tb_batch_import_job_folder_id", table_name="tb_batch_import_job")
    op.drop_index("ix_tb_batch_import_job_company_id", table_name="tb_batch_import_job")
    op.drop_table("tb_batch_import_job")
