"""通用 Attachment 多态模型单测。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.attachment import Attachment


def test_attachment_persists_entity_type_and_id(db: Session) -> None:
    att = Attachment(
        entity_type="work_order",
        entity_id="wo-1",
        file_name="r.pdf",
        storage_path="a/b.pdf",
        mime_type="application/pdf",
        size_bytes=3,
        description="",
        sort_order=0,
    )
    db.add(att)
    db.commit()
    row = db.execute(
        select(Attachment).where(
            Attachment.entity_type == "work_order", Attachment.entity_id == "wo-1"
        )
    ).scalar_one()
    assert row.id == att.id
    assert row.entity_type == "work_order"
    assert row.entity_id == "wo-1"
