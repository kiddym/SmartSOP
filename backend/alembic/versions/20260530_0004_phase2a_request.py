"""phase2a request: request(+activity) tables + work_order.request_id

Revision ID: phase2a_request
Revises: phase1b_workorder_loop
Create Date: 2026-05-30

Hand-authored (MySQL prod + SQLite dev/test). New tables -> create_table;
work_order.request_id -> add_column. Works on both dialects, no branching.
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import DATETIME6

revision: str = "phase2a_request"
down_revision: str | Sequence[str] | None = "phase1b_workorder_loop"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ts() -> list[sa.Column]:
    return [
        sa.Column("created_at", DATETIME6, nullable=False),
        sa.Column("updated_at", DATETIME6, nullable=False),
    ]


def _soft() -> list[sa.Column]:
    return [
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", DATETIME6, nullable=True),
    ]


def _company_fk() -> sa.Column:
    return sa.Column(
        "company_id", sa.String(36),
        sa.ForeignKey("tb_company.id", ondelete="CASCADE"), nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "tb_request",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("custom_id", sa.String(20), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=sa.text("('')")),
        sa.Column("priority",
                  sa.Enum("NONE", "LOW", "MEDIUM", "HIGH", name="workorderpriority"),
                  nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("asset_id", sa.String(36),
                  sa.ForeignKey("tb_asset.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("location_id", sa.String(36),
                  sa.ForeignKey("tb_location.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("status",
                  sa.Enum("PENDING", "APPROVED", "REJECTED", "CANCELED", name="requeststatus"),
                  nullable=False),
        sa.Column("work_order_id", sa.String(36), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=False, server_default=sa.text("('')")),
        sa.Column("resolved_by_user_id", sa.String(36), nullable=True),
        sa.Column("resolved_at", DATETIME6, nullable=True),
        *_ts(), *_soft(),
    )
    op.create_index("ix_tb_request_company_id", "tb_request", ["company_id"])
    op.create_index("ix_tb_request_asset_id", "tb_request", ["asset_id"])
    op.create_index("ix_tb_request_location_id", "tb_request", ["location_id"])
    op.create_index("ix_tb_request_work_order_id", "tb_request", ["work_order_id"])

    op.create_table(
        "tb_request_activity",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("request_id", sa.String(36),
                  sa.ForeignKey("tb_request.id", ondelete="CASCADE"), nullable=False),
        sa.Column("activity_type", sa.String(20), nullable=False),
        sa.Column("actor_user_id", sa.String(36), nullable=True),
        sa.Column("from_status", sa.String(20), nullable=True),
        sa.Column("to_status", sa.String(20), nullable=True),
        sa.Column("comment", sa.Text(), nullable=False, server_default=sa.text("('')")),
        *_ts(),
    )
    op.create_index("ix_tb_request_activity_company_id", "tb_request_activity", ["company_id"])
    op.create_index("ix_tb_request_activity_request_id", "tb_request_activity", ["request_id"])

    op.add_column("tb_work_order", sa.Column("request_id", sa.String(36), nullable=True))
    op.create_index("ix_tb_work_order_request_id", "tb_work_order", ["request_id"])


def downgrade() -> None:
    # work_order.request_id 为弱引用（无 FK），其索引普通、删列无碍，两方言一致。
    op.drop_index("ix_tb_work_order_request_id", table_name="tb_work_order")
    op.drop_column("tb_work_order", "request_id")
    # tb_request(_activity) 的 company_id/request_id 等列索引被 FK 占用（MySQL 1553），
    # DROP TABLE 连带清理，故仅 SQLite 显式删索引（保持其既有验证行为）。
    is_sqlite = op.get_bind().dialect.name == "sqlite"
    if is_sqlite:
        op.drop_index("ix_tb_request_activity_request_id", table_name="tb_request_activity")
        op.drop_index("ix_tb_request_activity_company_id", table_name="tb_request_activity")
    op.drop_table("tb_request_activity")
    if is_sqlite:
        op.drop_index("ix_tb_request_work_order_id", table_name="tb_request")
        op.drop_index("ix_tb_request_location_id", table_name="tb_request")
        op.drop_index("ix_tb_request_asset_id", table_name="tb_request")
        op.drop_index("ix_tb_request_company_id", table_name="tb_request")
    op.drop_table("tb_request")
