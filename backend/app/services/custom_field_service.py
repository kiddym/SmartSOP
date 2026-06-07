"""业务实体自定义字段定义 CRUD + 值校验入口。"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import bad_request, conflict, not_found, unprocessable
from app.models.base import utcnow
from app.models.custom_field_def import CustomFieldDef
from app.schemas.custom_field import ENTITY_TYPES, CustomFieldCreate, CustomFieldUpdate
from app.services import field_service
from app.services import field_validation as fv

KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def assert_entity(entity_type: str) -> None:
    if entity_type not in ENTITY_TYPES:
        raise bad_request("INVALID_ENTITY_TYPE", "不支持的实体类型", field="entity_type")


def _defs(db: Session, entity_type: str, *, only_active_status: bool) -> list[CustomFieldDef]:
    q = select(CustomFieldDef).where(
        CustomFieldDef.is_active.is_(True), CustomFieldDef.entity_type == entity_type
    )
    if only_active_status:
        q = q.where(CustomFieldDef.status == "active")
    q = q.order_by(CustomFieldDef.sort_order, CustomFieldDef.created_at)
    return list(db.execute(q).scalars())


def list_defs(db: Session, entity_type: str, *, include_archived: bool) -> list[CustomFieldDef]:
    assert_entity(entity_type)
    return _defs(db, entity_type, only_active_status=not include_archived)


def get_or_404(db: Session, field_id: str) -> CustomFieldDef:
    row = db.execute(
        select(CustomFieldDef).where(
            CustomFieldDef.id == field_id, CustomFieldDef.is_active.is_(True)
        )
    ).scalar_one_or_none()
    if row is None:
        raise not_found("NOT_FOUND", "自定义字段不存在")
    return row


def create(db: Session, payload: CustomFieldCreate) -> CustomFieldDef:
    assert_entity(payload.entity_type)
    if KEY_RE.match(payload.key) is None:
        raise unprocessable(
            "VALIDATION_FAILED", "key 须为小写字母开头的字母/数字/下划线", field="key"
        )
    dup = db.execute(
        select(CustomFieldDef.id).where(
            CustomFieldDef.is_active.is_(True),
            CustomFieldDef.entity_type == payload.entity_type,
            CustomFieldDef.key == payload.key,
        )
    ).first()
    if dup is not None:
        raise conflict("FIELD_KEY_DUPLICATE", "该实体下字段 key 已存在", field="key")
    row = CustomFieldDef(
        entity_type=payload.entity_type,
        key=payload.key,
        name=payload.name,
        field_type=payload.field_type,
        description=payload.description,
        required=payload.required,
        default_value=payload.default_value,
        options=[o.model_dump() for o in payload.options],
        validation_rules=field_service.compile_form_to_schema(
            payload.field_type, payload.validation
        ),
        sort_order=payload.sort_order,
        status="active",
    )
    db.add(row)
    db.flush()
    return row


def update(db: Session, field_id: str, payload: CustomFieldUpdate) -> CustomFieldDef:
    row = get_or_404(db, field_id)
    row.name = payload.name
    row.description = payload.description
    row.required = payload.required
    row.default_value = payload.default_value
    row.options = field_service.merge_options(row.options, payload.options)
    row.validation_rules = field_service.compile_form_to_schema(row.field_type, payload.validation)
    row.sort_order = payload.sort_order
    db.flush()
    return row


def set_status(db: Session, field_id: str, status: str) -> CustomFieldDef:
    row = get_or_404(db, field_id)
    row.status = status
    db.flush()
    return row


def delete(db: Session, field_id: str) -> None:
    row = get_or_404(db, field_id)
    row.is_active = False
    row.deleted_at = utcnow()
    db.flush()


def reorder(db: Session, entity_type: str, ordered_ids: list[str]) -> list[CustomFieldDef]:
    assert_entity(entity_type)
    rows = {
        r.id: r
        for r in db.execute(
            select(CustomFieldDef).where(
                CustomFieldDef.id.in_(ordered_ids),
                CustomFieldDef.is_active.is_(True),
                CustomFieldDef.entity_type == entity_type,
            )
        ).scalars()
    }
    order = 0
    for fid in ordered_ids:
        r = rows.get(fid)
        if r is not None:
            r.sort_order = order
            order += 1
    db.flush()
    return list_defs(db, entity_type, include_archived=False)


def validate_values(
    db: Session, entity_type: str, custom_values: dict[str, Any], *, require_check: bool = True
) -> None:
    """写宿主前调用：按 entity_type 的 active 定义校验；未知 key（无任何定义）拒绝 422。"""
    assert_entity(entity_type)
    all_defs = _defs(db, entity_type, only_active_status=False)  # active + archived
    known = {d.key for d in all_defs}
    unknown = [k for k in custom_values if k not in known]
    if unknown:
        raise unprocessable("UNKNOWN_CUSTOM_FIELD", f"未知自定义字段: {', '.join(unknown)}")
    active = [d for d in all_defs if d.status == "active"]
    fv.validate_against_definitions(active, custom_values, require_check=require_check)
