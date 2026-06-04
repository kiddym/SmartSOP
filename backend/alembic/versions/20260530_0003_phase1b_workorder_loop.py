"""phase1b workorder loop: work_order(+assignee/team), step_result, activity

Revision ID: phase1b_workorder_loop
Revises: phase1a_base_domain
Create Date: 2026-05-30

Hand-authored (MySQL prod + SQLite dev/test). All new tables -> create_table
works on both dialects, no dialect branching needed.
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import DATETIME6

revision: str = "phase1b_workorder_loop"
down_revision: str | Sequence[str] | None = "phase1a_base_domain"
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
        "tb_work_order",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("custom_id", sa.String(20), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=sa.text("('')")),
        sa.Column("status",
                  sa.Enum("OPEN", "IN_PROGRESS", "ON_HOLD", "COMPLETE", "CANCELED",
                          name="workorderstatus"),
                  nullable=False),
        sa.Column("priority",
                  sa.Enum("NONE", "LOW", "MEDIUM", "HIGH", name="workorderpriority"),
                  nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("asset_id", sa.String(36),
                  sa.ForeignKey("tb_asset.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("location_id", sa.String(36),
                  sa.ForeignKey("tb_location.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("primary_user_id", sa.String(36),
                  sa.ForeignKey("tb_user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("procedure_id", sa.String(36), nullable=True),
        sa.Column("procedure_group_id", sa.String(36), nullable=True),
        sa.Column("procedure_attached_at", DATETIME6, nullable=True),
        sa.Column("completed_at", DATETIME6, nullable=True),
        *_ts(), *_soft(),
    )
    op.create_index("ix_tb_work_order_company_id", "tb_work_order", ["company_id"])
    op.create_index("ix_tb_work_order_asset_id", "tb_work_order", ["asset_id"])
    op.create_index("ix_tb_work_order_location_id", "tb_work_order", ["location_id"])
    op.create_index("ix_tb_work_order_primary_user_id", "tb_work_order", ["primary_user_id"])
    op.create_index("ix_tb_work_order_procedure_id", "tb_work_order", ["procedure_id"])
    op.create_index("ix_tb_work_order_is_active", "tb_work_order", ["is_active"])

    op.create_table(
        "tb_work_order_assignee",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("work_order_id", sa.String(36),
                  sa.ForeignKey("tb_work_order.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36),
                  sa.ForeignKey("tb_user.id", ondelete="CASCADE"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("work_order_id", "user_id", name="uq_work_order_assignee"),
    )
    op.create_index("ix_tb_work_order_assignee_company_id", "tb_work_order_assignee", ["company_id"])
    op.create_index("ix_tb_work_order_assignee_work_order_id", "tb_work_order_assignee", ["work_order_id"])
    op.create_index("ix_tb_work_order_assignee_user_id", "tb_work_order_assignee", ["user_id"])

    op.create_table(
        "tb_work_order_team",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("work_order_id", sa.String(36),
                  sa.ForeignKey("tb_work_order.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", sa.String(36),
                  sa.ForeignKey("tb_team.id", ondelete="CASCADE"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("work_order_id", "team_id", name="uq_work_order_team"),
    )
    op.create_index("ix_tb_work_order_team_company_id", "tb_work_order_team", ["company_id"])
    op.create_index("ix_tb_work_order_team_work_order_id", "tb_work_order_team", ["work_order_id"])
    op.create_index("ix_tb_work_order_team_team_id", "tb_work_order_team", ["team_id"])

    op.create_table(
        "tb_work_order_step_result",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("work_order_id", sa.String(36),
                  sa.ForeignKey("tb_work_order.id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_id", sa.String(36), nullable=False),
        sa.Column("node_code", sa.String(50), nullable=False, server_default=""),
        sa.Column("node_sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("response", sa.JSON(), nullable=True),
        sa.Column("is_done", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("done_by_user_id", sa.String(36), nullable=True),
        sa.Column("done_at", DATETIME6, nullable=True),
        sa.Column("notes", sa.Text(), nullable=False, server_default=sa.text("('')")),
        *_ts(),
        sa.UniqueConstraint("work_order_id", "node_id", name="uq_work_order_step_result_node"),
    )
    op.create_index("ix_tb_work_order_step_result_company_id", "tb_work_order_step_result", ["company_id"])
    op.create_index("ix_tb_work_order_step_result_work_order_id", "tb_work_order_step_result", ["work_order_id"])
    op.create_index("ix_tb_work_order_step_result_node_id", "tb_work_order_step_result", ["node_id"])

    op.create_table(
        "tb_work_order_activity",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("work_order_id", sa.String(36),
                  sa.ForeignKey("tb_work_order.id", ondelete="CASCADE"), nullable=False),
        sa.Column("activity_type", sa.String(20), nullable=False),
        sa.Column("actor_user_id", sa.String(36), nullable=True),
        sa.Column("from_status", sa.String(20), nullable=True),
        sa.Column("to_status", sa.String(20), nullable=True),
        sa.Column("comment", sa.Text(), nullable=False, server_default=sa.text("('')")),
        *_ts(),
    )
    op.create_index("ix_tb_work_order_activity_company_id", "tb_work_order_activity", ["company_id"])
    op.create_index("ix_tb_work_order_activity_work_order_id", "tb_work_order_activity", ["work_order_id"])


def downgrade() -> None:
    for tbl in (
        "tb_work_order_activity", "tb_work_order_step_result",
        "tb_work_order_team", "tb_work_order_assignee", "tb_work_order",
    ):
        op.drop_table(tbl)
