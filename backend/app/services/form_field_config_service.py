"""表单字段配置服务：默认字段定义 + 种子化 + 批量更新。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.form_field_config import FormFieldConfig
from app.schemas.form_field_config import FieldConfigItem

# 每个表单的可配置字段（field_name, 默认 visible, 默认 required）按渲染顺序。
# title/description 等强制项不纳入（始终显示）；这里是“可被管理员开关”的字段集。
_FORM_FIELDS: dict[str, list[tuple[str, bool, bool]]] = {
    "REQUEST": [
        ("description", True, False),
        ("priority", True, False),
        ("due_date", True, False),
        ("asset", True, False),
        ("location", True, False),
    ],
    "WORK_ORDER": [
        ("description", True, False),
        ("priority", True, False),
        ("due_date", True, False),
        ("asset", True, False),
        ("location", True, False),
        ("assignee", True, False),
        ("team", True, False),
        ("category", True, False),
        ("estimated_duration", True, False),
        ("estimated_start_date", True, False),
    ],
}


def is_known_form(form_key: str) -> bool:
    return form_key in _FORM_FIELDS


def known_field_names(form_key: str) -> set[str]:
    return {name for name, _v, _r in _FORM_FIELDS.get(form_key, [])}


def get_config(db: Session, company_id: str, form_key: str) -> list[FormFieldConfig]:
    """返回该表单的全部字段配置，按定义顺序；缺失的字段按默认种子化。"""
    existing = {
        row.field_name: row
        for row in db.execute(
            select(FormFieldConfig).where(
                FormFieldConfig.company_id == company_id,
                FormFieldConfig.form_key == form_key,
            )
        ).scalars()
    }
    result: list[FormFieldConfig] = []
    for order, (name, default_visible, default_required) in enumerate(_FORM_FIELDS[form_key]):
        row = existing.get(name)
        if row is None:
            row = FormFieldConfig(
                company_id=company_id,
                form_key=form_key,
                field_name=name,
                visible=default_visible,
                required=default_required,
                sort_order=order,
            )
            db.add(row)
            db.flush()
        result.append(row)
    return result


def update_config(
    db: Session, company_id: str, form_key: str, items: list[FieldConfigItem]
) -> list[FormFieldConfig]:
    """按 field_name 批量 upsert visible/required，未提及字段保持不变。"""
    get_config(db, company_id, form_key)  # 确保种子存在
    rows = {
        row.field_name: row
        for row in db.execute(
            select(FormFieldConfig).where(
                FormFieldConfig.company_id == company_id,
                FormFieldConfig.form_key == form_key,
            )
        ).scalars()
    }
    for item in items:
        row = rows.get(item.field_name)
        if row is not None:
            row.visible = item.visible
            row.required = item.required
    db.flush()
    return get_config(db, company_id, form_key)
