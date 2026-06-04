"""phase2b pm: preventive_maintenance + pm_assignee/pm_team/pm_activity tables

Revision ID: phase2b_pm
Revises: phase2a_request
Create Date: 2026-05-31

Hand-authored (MySQL prod + SQLite dev/test). New tables -> create_table.
Works on both dialects, no branching.
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import DATETIME6

revision: str = "phase2b_pm"
down_revision: str | Sequence[str] | None = "phase2a_request"
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
        "tb_preventive_maintenance",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("custom_id", sa.String(20), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=sa.text("('')")),
        sa.Column("priority",
                  sa.Enum("NONE", "LOW", "MEDIUM", "HIGH", name="workorderpriority"),
                  nullable=False),
        sa.Column("asset_id", sa.String(36),
                  sa.ForeignKey("tb_asset.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("location_id", sa.String(36),
                  sa.ForeignKey("tb_location.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("primary_user_id", sa.String(36),
                  sa.ForeignKey("tb_user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("procedure_id", sa.String(36), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("frequency_unit",
                  sa.Enum("DAY", "WEEK", "MONTH", name="pmfrequencyunit"),
                  nullable=False),
        sa.Column("frequency_value", sa.Integer(), nullable=False),
        sa.Column("next_due_date", sa.Date(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("last_generated_at", DATETIME6, nullable=True),
        sa.Column("last_work_order_id", sa.String(36), nullable=True),
        *_ts(), *_soft(),
    )
    op.create_index("ix_tb_pm_company_id", "tb_preventive_maintenance", ["company_id"])
    op.create_index("ix_tb_pm_asset_id", "tb_preventive_maintenance", ["asset_id"])
    op.create_index("ix_tb_pm_location_id", "tb_preventive_maintenance", ["location_id"])
    op.create_index("ix_tb_pm_primary_user_id", "tb_preventive_maintenance", ["primary_user_id"])
    op.create_index("ix_tb_pm_procedure_id", "tb_preventive_maintenance", ["procedure_id"])

    op.create_table(
        "tb_pm_assignee",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("pm_id", sa.String(36),
                  sa.ForeignKey("tb_preventive_maintenance.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("user_id", sa.String(36),
                  sa.ForeignKey("tb_user.id", ondelete="CASCADE"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("pm_id", "user_id", name="uq_pm_assignee"),
    )
    op.create_index("ix_tb_pm_assignee_company_id", "tb_pm_assignee", ["company_id"])
    op.create_index("ix_tb_pm_assignee_pm_id", "tb_pm_assignee", ["pm_id"])
    op.create_index("ix_tb_pm_assignee_user_id", "tb_pm_assignee", ["user_id"])

    op.create_table(
        "tb_pm_team",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("pm_id", sa.String(36),
                  sa.ForeignKey("tb_preventive_maintenance.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("team_id", sa.String(36),
                  sa.ForeignKey("tb_team.id", ondelete="CASCADE"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("pm_id", "team_id", name="uq_pm_team"),
    )
    op.create_index("ix_tb_pm_team_company_id", "tb_pm_team", ["company_id"])
    op.create_index("ix_tb_pm_team_pm_id", "tb_pm_team", ["pm_id"])
    op.create_index("ix_tb_pm_team_team_id", "tb_pm_team", ["team_id"])

    op.create_table(
        "tb_pm_activity",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("pm_id", sa.String(36),
                  sa.ForeignKey("tb_preventive_maintenance.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("activity_type", sa.String(20), nullable=False),
        sa.Column("actor_user_id", sa.String(36), nullable=True),
        sa.Column("comment", sa.Text(), nullable=False, server_default=sa.text("('')")),
        *_ts(),
    )
    op.create_index("ix_tb_pm_activity_company_id", "tb_pm_activity", ["company_id"])
    op.create_index("ix_tb_pm_activity_pm_id", "tb_pm_activity", ["pm_id"])


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("ix_tb_pm_activity_pm_id", table_name="tb_pm_activity")
        op.drop_index("ix_tb_pm_activity_company_id", table_name="tb_pm_activity")
    op.drop_table("tb_pm_activity")
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("ix_tb_pm_team_team_id", table_name="tb_pm_team")
        op.drop_index("ix_tb_pm_team_pm_id", table_name="tb_pm_team")
        op.drop_index("ix_tb_pm_team_company_id", table_name="tb_pm_team")
    op.drop_table("tb_pm_team")
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("ix_tb_pm_assignee_user_id", table_name="tb_pm_assignee")
        op.drop_index("ix_tb_pm_assignee_pm_id", table_name="tb_pm_assignee")
        op.drop_index("ix_tb_pm_assignee_company_id", table_name="tb_pm_assignee")
    op.drop_table("tb_pm_assignee")
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("ix_tb_pm_procedure_id", table_name="tb_preventive_maintenance")
        op.drop_index("ix_tb_pm_primary_user_id", table_name="tb_preventive_maintenance")
        op.drop_index("ix_tb_pm_location_id", table_name="tb_preventive_maintenance")
        op.drop_index("ix_tb_pm_asset_id", table_name="tb_preventive_maintenance")
        op.drop_index("ix_tb_pm_company_id", table_name="tb_preventive_maintenance")
    op.drop_table("tb_preventive_maintenance")
