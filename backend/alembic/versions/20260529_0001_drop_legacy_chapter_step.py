"""drop legacy chapter/step tables (B4)

ProcedureNode is the sole persistence model after B4. Removes tb_procedure_chapter /
tb_procedure_step. Dev-only; data is not migrated (dev.db rebuilt from head).
"""
from __future__ import annotations

from alembic import op

revision: str = "drop_legacy_chapter_step"
down_revision: str | None = "add_procedure_node"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("tb_procedure_step")  # FK chapter_id -> tb_procedure_chapter: drop first
    op.drop_table("tb_procedure_chapter")


def downgrade() -> None:
    # Irreversible by design: pytest builds its schema from ORM models
    # (Base.metadata.create_all), not migrations, so this downgrade is never exercised;
    # dev.db is rebuilt from head; there is no production data. A faithful recreate would
    # be initial_schema + four subsequent alters -- fragile DDL for zero practical value.
    raise NotImplementedError(
        "B4 removed the legacy chapter/step tables; downgrade past this revision is "
        "unsupported -- rebuild dev.db from head."
    )
