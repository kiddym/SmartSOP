"""宿主不存在 → 附件孤儿化软删。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app import tenant
from app.models.attachment import Attachment
from app.models.maintenance_asset import Asset
from app.services import attachment_service as svc


def test_soft_delete_when_host_missing(db: Session) -> None:
    tenant.set_current_company_id("co-1")
    db.add(Asset(custom_id="A1", name="泵"))
    db.commit()
    aid = db.query(Asset).one().id
    db.add(
        Attachment(
            entity_type="asset",
            entity_id=aid,
            file_name="a.pdf",
            storage_path="x/a.pdf",
            mime_type="application/pdf",
            size_bytes=1,
        )
    )
    db.add(
        Attachment(
            entity_type="asset",
            entity_id="ghost",
            file_name="b.pdf",
            storage_path="x/b.pdf",
            mime_type="application/pdf",
            size_bytes=1,
        )
    )
    db.commit()
    tenant.set_current_company_id(None)

    n = svc.soft_delete_orphaned_by_host(db)
    db.commit()
    assert n == 1
    with tenant.bypass_tenant_scope():
        alive = {a.entity_id for a in db.query(Attachment).filter(Attachment.is_active.is_(True))}
    assert alive == {aid}


def test_soft_delete_when_host_soft_deleted(db: Session) -> None:
    from app.models.base import utcnow

    tenant.set_current_company_id("co-1")
    asset = Asset(custom_id="A2", name="泵2")
    db.add(asset)
    db.flush()
    aid = asset.id
    db.add(
        Attachment(
            entity_type="asset",
            entity_id=aid,
            file_name="c.pdf",
            storage_path="x/c.pdf",
            mime_type="application/pdf",
            size_bytes=1,
        )
    )
    asset.is_active = False
    asset.deleted_at = utcnow()
    db.commit()
    tenant.set_current_company_id(None)

    n = svc.soft_delete_orphaned_by_host(db)
    db.commit()
    assert n == 1
    with tenant.bypass_tenant_scope():
        alive = list(db.query(Attachment).filter(Attachment.is_active.is_(True)))
    assert alive == []
