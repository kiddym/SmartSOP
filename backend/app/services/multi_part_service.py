"""多备件套件服务：CRUD（customId KIT）、成员（part_ids 全量替换）。纯分组。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.multi_part import MultiPart, MultiPartItem
from app.schemas.part import MultiPartCreate, MultiPartUpdate
from app.services import sequence_service


def part_ids(db: Session, multi_part_id: str) -> list[str]:
    return list(db.execute(
        select(MultiPartItem.part_id).where(MultiPartItem.multi_part_id == multi_part_id)
        .order_by(MultiPartItem.part_id)).scalars().all())


def _set_items(db: Session, multi_part_id: str, company_id: str,
               part_id_list: list[str]) -> None:
    for pid in dict.fromkeys(part_id_list):
        db.add(MultiPartItem(multi_part_id=multi_part_id, part_id=pid, company_id=company_id))


def create_multi_part(db: Session, payload: MultiPartCreate, company_id: str,
                      actor_user_id: str | None) -> MultiPart:
    seq = sequence_service.next_value(db, "multi_part", company_id)
    mp = MultiPart(
        custom_id=sequence_service.format_custom_id("KIT", seq),
        name=payload.name, description=payload.description, company_id=company_id,
    )
    db.add(mp)
    db.flush()
    _set_items(db, mp.id, company_id, payload.part_ids)
    db.commit()
    db.refresh(mp)
    return mp


def list_multi_parts(db: Session) -> list[MultiPart]:
    return list(db.execute(
        select(MultiPart).where(MultiPart.is_active.is_(True))
        .order_by(MultiPart.custom_id)).scalars().all())


def get_multi_part(db: Session, multi_part_id: str) -> MultiPart | None:
    mp = db.get(MultiPart, multi_part_id)
    if mp is None or not mp.is_active:
        return None
    return mp


def update_multi_part(db: Session, mp: MultiPart, payload: MultiPartUpdate,
                      company_id: str, actor_user_id: str | None) -> MultiPart:
    data = payload.model_dump(exclude_unset=True)
    new_parts = data.pop("part_ids", None)
    for k, v in data.items():
        setattr(mp, k, v)
    if new_parts is not None:
        db.execute(MultiPartItem.__table__.delete()
                   .where(MultiPartItem.multi_part_id == mp.id))
        _set_items(db, mp.id, company_id, new_parts)
    db.commit()
    db.refresh(mp)
    return mp


def delete_multi_part(db: Session, mp: MultiPart) -> None:
    mp.is_active = False
    mp.deleted_at = utcnow()
    db.commit()
