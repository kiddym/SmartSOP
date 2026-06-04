"""phase2c meter: meter + meter_reading + meter_trigger/assignee/team tables

Revision ID: phase2c_meter
Revises: phase2b_pm
Create Date: 2026-05-31

Hand-authored (MySQL prod + SQLite dev/test). New tables -> create_table.
Works on both dialects, no branching.
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import DATETIME6

revision: str = "phase2c_meter"
down_revision: str | Sequence[str] | None = "phase2b_pm"
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
        "tb_meter",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("custom_id", sa.String(20), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("unit", sa.String(50), nullable=False, server_default=""),
        sa.Column("update_frequency_days", sa.Integer(), nullable=True),
        sa.Column("asset_id", sa.String(36),
                  sa.ForeignKey("tb_asset.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("location_id", sa.String(36),
                  sa.ForeignKey("tb_location.id", ondelete="RESTRICT"), nullable=True),
        *_ts(), *_soft(),
    )
    op.create_index("ix_tb_meter_company_id", "tb_meter", ["company_id"])
    op.create_index("ix_tb_meter_asset_id", "tb_meter", ["asset_id"])
    op.create_index("ix_tb_meter_location_id", "tb_meter", ["location_id"])

    op.create_table(
        "tb_meter_reading",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("meter_id", sa.String(36),
                  sa.ForeignKey("tb_meter.id", ondelete="CASCADE"), nullable=False),
        sa.Column("value", sa.Numeric(18, 4), nullable=False),
        sa.Column("reading_at", DATETIME6, nullable=False),
        sa.Column("recorded_by_user_id", sa.String(36), nullable=True),
        *_ts(),
    )
    op.create_index("ix_tb_meter_reading_company_id", "tb_meter_reading", ["company_id"])
    op.create_index("ix_tb_meter_reading_meter_id", "tb_meter_reading", ["meter_id"])

    op.create_table(
        "tb_meter_trigger",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("meter_id", sa.String(36),
                  sa.ForeignKey("tb_meter.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("comparator",
                  sa.Enum("LESS_THAN", "MORE_THAN", name="metercomparator"),
                  nullable=False),
        sa.Column("threshold", sa.Numeric(18, 4), nullable=False),
        sa.Column("is_armed", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("priority",
                  sa.Enum("NONE", "LOW", "MEDIUM", "HIGH", name="workorderpriority"),
                  nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=sa.text("('')")),
        sa.Column("primary_user_id", sa.String(36),
                  sa.ForeignKey("tb_user.id", ondelete="SET NULL"), nullable=True),
        sa.Column("procedure_id", sa.String(36), nullable=True),
        sa.Column("last_triggered_at", DATETIME6, nullable=True),
        sa.Column("last_work_order_id", sa.String(36), nullable=True),
        *_ts(), *_soft(),
    )
    op.create_index("ix_tb_meter_trigger_company_id", "tb_meter_trigger", ["company_id"])
    op.create_index("ix_tb_meter_trigger_meter_id", "tb_meter_trigger", ["meter_id"])
    op.create_index("ix_tb_meter_trigger_primary_user_id", "tb_meter_trigger", ["primary_user_id"])
    op.create_index("ix_tb_meter_trigger_procedure_id", "tb_meter_trigger", ["procedure_id"])

    op.create_table(
        "tb_meter_trigger_assignee",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("trigger_id", sa.String(36),
                  sa.ForeignKey("tb_meter_trigger.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36),
                  sa.ForeignKey("tb_user.id", ondelete="CASCADE"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("trigger_id", "user_id", name="uq_meter_trigger_assignee"),
    )
    op.create_index("ix_tb_meter_trigger_assignee_company_id", "tb_meter_trigger_assignee", ["company_id"])
    op.create_index("ix_tb_meter_trigger_assignee_trigger_id", "tb_meter_trigger_assignee", ["trigger_id"])
    op.create_index("ix_tb_meter_trigger_assignee_user_id", "tb_meter_trigger_assignee", ["user_id"])

    op.create_table(
        "tb_meter_trigger_team",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("trigger_id", sa.String(36),
                  sa.ForeignKey("tb_meter_trigger.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", sa.String(36),
                  sa.ForeignKey("tb_team.id", ondelete="CASCADE"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("trigger_id", "team_id", name="uq_meter_trigger_team"),
    )
    op.create_index("ix_tb_meter_trigger_team_company_id", "tb_meter_trigger_team", ["company_id"])
    op.create_index("ix_tb_meter_trigger_team_trigger_id", "tb_meter_trigger_team", ["trigger_id"])
    op.create_index("ix_tb_meter_trigger_team_team_id", "tb_meter_trigger_team", ["team_id"])


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("ix_tb_meter_trigger_team_team_id", table_name="tb_meter_trigger_team")
        op.drop_index("ix_tb_meter_trigger_team_trigger_id", table_name="tb_meter_trigger_team")
        op.drop_index("ix_tb_meter_trigger_team_company_id", table_name="tb_meter_trigger_team")
    op.drop_table("tb_meter_trigger_team")
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("ix_tb_meter_trigger_assignee_user_id", table_name="tb_meter_trigger_assignee")
        op.drop_index("ix_tb_meter_trigger_assignee_trigger_id", table_name="tb_meter_trigger_assignee")
        op.drop_index("ix_tb_meter_trigger_assignee_company_id", table_name="tb_meter_trigger_assignee")
    op.drop_table("tb_meter_trigger_assignee")
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("ix_tb_meter_trigger_procedure_id", table_name="tb_meter_trigger")
        op.drop_index("ix_tb_meter_trigger_primary_user_id", table_name="tb_meter_trigger")
        op.drop_index("ix_tb_meter_trigger_meter_id", table_name="tb_meter_trigger")
        op.drop_index("ix_tb_meter_trigger_company_id", table_name="tb_meter_trigger")
    op.drop_table("tb_meter_trigger")
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("ix_tb_meter_reading_meter_id", table_name="tb_meter_reading")
        op.drop_index("ix_tb_meter_reading_company_id", table_name="tb_meter_reading")
    op.drop_table("tb_meter_reading")
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index("ix_tb_meter_location_id", table_name="tb_meter")
        op.drop_index("ix_tb_meter_asset_id", table_name="tb_meter")
        op.drop_index("ix_tb_meter_company_id", table_name="tb_meter")
    op.drop_table("tb_meter")
