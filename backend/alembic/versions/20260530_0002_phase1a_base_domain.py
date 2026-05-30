"""phase1a base domain: sequence, asset_category, team(+members),
location(+relations), asset(+relations), asset_downtime

Revision ID: phase1a_base_domain
Revises: phase0_platform
Create Date: 2026-05-30

Hand-authored (MySQL prod + SQLite dev/test). All new tables -> create_table
works on both dialects, no dialect branching needed.
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import DATETIME6

revision: str = "phase1a_base_domain"
down_revision: str | Sequence[str] | None = "phase0_platform"
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
        "tb_sequence",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("scope", sa.String(40), nullable=False),
        sa.Column("next_val", sa.Integer(), nullable=False),
        *_ts(),
        sa.UniqueConstraint("company_id", "scope", name="uq_sequence_company_scope"),
    )
    op.create_index("ix_tb_sequence_company_id", "tb_sequence", ["company_id"])

    op.create_table(
        "tb_asset_category",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("name", sa.String(128), nullable=False),
        *_ts(), *_soft(),
        sa.UniqueConstraint("company_id", "name", name="uq_asset_category_company_name"),
    )
    op.create_index("ix_tb_asset_category_company_id", "tb_asset_category", ["company_id"])
    op.create_index("ix_tb_asset_category_is_active", "tb_asset_category", ["is_active"])

    op.create_table(
        "tb_team",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        *_ts(), *_soft(),
        sa.UniqueConstraint("company_id", "name", name="uq_team_company_name"),
    )
    op.create_index("ix_tb_team_company_id", "tb_team", ["company_id"])
    op.create_index("ix_tb_team_is_active", "tb_team", ["is_active"])

    op.create_table(
        "tb_team_user",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("team_id", sa.String(36),
                  sa.ForeignKey("tb_team.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36),
                  sa.ForeignKey("tb_user.id", ondelete="CASCADE"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("team_id", "user_id", name="uq_team_user"),
    )
    op.create_index("ix_tb_team_user_company_id", "tb_team_user", ["company_id"])
    op.create_index("ix_tb_team_user_team_id", "tb_team_user", ["team_id"])
    op.create_index("ix_tb_team_user_user_id", "tb_team_user", ["user_id"])

    op.create_table(
        "tb_location",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("custom_id", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("parent_id", sa.String(36),
                  sa.ForeignKey("tb_location.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("address", sa.String(500), nullable=False, server_default=""),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        *_ts(), *_soft(),
    )
    op.create_index("ix_tb_location_company_id", "tb_location", ["company_id"])
    op.create_index("ix_tb_location_parent_id", "tb_location", ["parent_id"])
    op.create_index("ix_tb_location_is_active", "tb_location", ["is_active"])

    op.create_table(
        "tb_location_user",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("location_id", sa.String(36),
                  sa.ForeignKey("tb_location.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36),
                  sa.ForeignKey("tb_user.id", ondelete="CASCADE"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("location_id", "user_id", name="uq_location_user"),
    )
    op.create_index("ix_tb_location_user_company_id", "tb_location_user", ["company_id"])
    op.create_index("ix_tb_location_user_location_id", "tb_location_user", ["location_id"])
    op.create_index("ix_tb_location_user_user_id", "tb_location_user", ["user_id"])

    op.create_table(
        "tb_location_team",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("location_id", sa.String(36),
                  sa.ForeignKey("tb_location.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", sa.String(36),
                  sa.ForeignKey("tb_team.id", ondelete="CASCADE"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("location_id", "team_id", name="uq_location_team"),
    )
    op.create_index("ix_tb_location_team_company_id", "tb_location_team", ["company_id"])
    op.create_index("ix_tb_location_team_location_id", "tb_location_team", ["location_id"])
    op.create_index("ix_tb_location_team_team_id", "tb_location_team", ["team_id"])

    op.create_table(
        "tb_asset",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("custom_id", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("parent_id", sa.String(36),
                  sa.ForeignKey("tb_asset.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("location_id", sa.String(36),
                  sa.ForeignKey("tb_location.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("category_id", sa.String(36),
                  sa.ForeignKey("tb_asset_category.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status",
                  sa.Enum("OPERATIONAL", "STANDBY", "MODERNIZATION", "INSPECTION_SCHEDULED",
                          "COMMISSIONING", "EMERGENCY_SHUTDOWN", "DOWN", name="assetstatus"),
                  nullable=False),
        sa.Column("serial_number", sa.String(200), nullable=False, server_default=""),
        sa.Column("model", sa.String(200), nullable=False, server_default=""),
        sa.Column("manufacturer", sa.String(200), nullable=False, server_default=""),
        sa.Column("power", sa.String(100), nullable=False, server_default=""),
        sa.Column("warranty_expiration_date", sa.Date(), nullable=True),
        sa.Column("in_service_date", sa.Date(), nullable=True),
        sa.Column("acquisition_cost", sa.Numeric(18, 2), nullable=True),
        sa.Column("barcode", sa.String(120), nullable=True),
        sa.Column("nfc_id", sa.String(120), nullable=True),
        sa.Column("primary_user_id", sa.String(36),
                  sa.ForeignKey("tb_user.id", ondelete="SET NULL"), nullable=True),
        *_ts(), *_soft(),
    )
    op.create_index("ix_tb_asset_company_id", "tb_asset", ["company_id"])
    op.create_index("ix_tb_asset_parent_id", "tb_asset", ["parent_id"])
    op.create_index("ix_tb_asset_location_id", "tb_asset", ["location_id"])
    op.create_index("ix_tb_asset_category_id", "tb_asset", ["category_id"])
    op.create_index("ix_tb_asset_barcode", "tb_asset", ["barcode"])
    op.create_index("ix_tb_asset_nfc_id", "tb_asset", ["nfc_id"])
    op.create_index("ix_tb_asset_primary_user_id", "tb_asset", ["primary_user_id"])
    op.create_index("ix_tb_asset_is_active", "tb_asset", ["is_active"])

    op.create_table(
        "tb_asset_user",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("asset_id", sa.String(36),
                  sa.ForeignKey("tb_asset.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36),
                  sa.ForeignKey("tb_user.id", ondelete="CASCADE"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("asset_id", "user_id", name="uq_asset_user"),
    )
    op.create_index("ix_tb_asset_user_company_id", "tb_asset_user", ["company_id"])
    op.create_index("ix_tb_asset_user_asset_id", "tb_asset_user", ["asset_id"])
    op.create_index("ix_tb_asset_user_user_id", "tb_asset_user", ["user_id"])

    op.create_table(
        "tb_asset_team",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("asset_id", sa.String(36),
                  sa.ForeignKey("tb_asset.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", sa.String(36),
                  sa.ForeignKey("tb_team.id", ondelete="CASCADE"), nullable=False),
        *_ts(),
        sa.UniqueConstraint("asset_id", "team_id", name="uq_asset_team"),
    )
    op.create_index("ix_tb_asset_team_company_id", "tb_asset_team", ["company_id"])
    op.create_index("ix_tb_asset_team_asset_id", "tb_asset_team", ["asset_id"])
    op.create_index("ix_tb_asset_team_team_id", "tb_asset_team", ["team_id"])

    op.create_table(
        "tb_asset_downtime",
        sa.Column("id", sa.String(36), primary_key=True),
        _company_fk(),
        sa.Column("asset_id", sa.String(36),
                  sa.ForeignKey("tb_asset.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("started_at", DATETIME6, nullable=False),
        sa.Column("ended_at", DATETIME6, nullable=True),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("downtime_type", sa.String(20), nullable=False, server_default="manual"),
        *_ts(),
    )
    op.create_index("ix_tb_asset_downtime_company_id", "tb_asset_downtime", ["company_id"])
    op.create_index("ix_tb_asset_downtime_asset_id", "tb_asset_downtime", ["asset_id"])


def downgrade() -> None:
    for tbl in (
        "tb_asset_downtime", "tb_asset_team", "tb_asset_user", "tb_asset",
        "tb_location_team", "tb_location_user", "tb_location",
        "tb_team_user", "tb_team", "tb_asset_category", "tb_sequence",
    ):
        op.drop_table(tbl)
