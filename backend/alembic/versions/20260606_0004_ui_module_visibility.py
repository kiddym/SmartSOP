"""ui module visibility flags on company settings

Revision ID: ui_module_visibility
Revises: form_field_config
Create Date: 2026-06-06

tb_company_settings 加 4 个导航模块显隐开关（server_default '1'，既有行默认全显）。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "ui_module_visibility"
down_revision: str | Sequence[str] | None = "form_field_config"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLS = ("show_requests", "show_locations", "show_meters", "show_vendors_customers")


def upgrade() -> None:
    with op.batch_alter_table("tb_company_settings") as batch_op:
        for col in _COLS:
            batch_op.add_column(
                sa.Column(col, sa.Boolean(), server_default="1", nullable=False)
            )


def downgrade() -> None:
    with op.batch_alter_table("tb_company_settings") as batch_op:
        for col in reversed(_COLS):
            batch_op.drop_column(col)
