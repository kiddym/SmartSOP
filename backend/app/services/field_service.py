"""自定义字段服务（api-specification §5.7 / §38 / §17 / Q253-Q258 / Q367-Q368）。

承担：字段 CRUD + 批量（update-status / batch-delete / reorder）+ key/field_type 不可变
约束 + options 删除软代理 archived（Q255）+ 表单化校验项 compile 成 JSON Schema +
custom_values 校验（手写子集校验器，Q367）。

字段配置变更**不写审计**（Q122 未列字段动作）。事务边界：只 flush，由 router 提交。
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import bad_request, conflict, not_found, unprocessable
from app.models.base import utcnow
from app.models.field import ProcedureField
from app.schemas.common import BatchDeleteFailure, BatchDeleteResult
from app.schemas.field import FieldCreate, FieldOption, FieldUpdate, FieldValidation

KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")  # 小写字母开头 + 字母/数字/下划线（Q254）
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# --------------------------------------------------------------------------- #
# 校验规则 compile（Q253）
# --------------------------------------------------------------------------- #
def compile_form_to_schema(field_type: str, v: FieldValidation) -> dict[str, Any]:
    """把表单化校验项转成标准 JSON Schema（仅覆盖 Q253 子集，Q367）。"""
    schema: dict[str, Any] = {}
    if field_type in ("text", "textarea"):
        schema["type"] = "string"
        if v.min_length is not None:
            schema["minLength"] = v.min_length
        if v.max_length is not None:
            schema["maxLength"] = v.max_length
        if v.pattern:
            schema["pattern"] = v.pattern
    elif field_type == "number":
        schema["type"] = "number"
        if v.minimum is not None:
            schema["minimum"] = v.minimum
        if v.maximum is not None:
            schema["maximum"] = v.maximum
    elif field_type == "date":
        schema["type"] = "string"
        schema["format"] = "date"
    elif field_type in ("multi_select", "checkbox"):
        schema["type"] = "array"
    # select：枚举在校验时按选项动态判定，不存静态 enum
    return schema


# --------------------------------------------------------------------------- #
# custom_values 校验（手写子集校验器，Q367/Q368）
# --------------------------------------------------------------------------- #
def _is_empty(val: Any) -> bool:
    return val is None or val == "" or val == []


def _err(field: ProcedureField, msg: str) -> None:
    raise unprocessable("CUSTOM_FIELD_INVALID", f"字段「{field.name}」{msg}", field=field.key)


def _option_values(field: ProcedureField) -> set[str]:
    # active 与 archived 选项值均放行（旧值保留只读，Q255）。
    return {str(o.get("value")) for o in (field.options or [])}


def _validate_one(field: ProcedureField, val: Any) -> None:
    schema = field.validation_rules or {}
    ftype = field.field_type
    if ftype in ("text", "textarea"):
        if not isinstance(val, str):
            _err(field, "应为文本")
        text = val
        if "minLength" in schema and len(text) < schema["minLength"]:
            _err(field, f"长度不足 {schema['minLength']}")
        if "maxLength" in schema and len(text) > schema["maxLength"]:
            _err(field, f"长度超过 {schema['maxLength']}")
        if "pattern" in schema and re.search(schema["pattern"], text) is None:
            _err(field, "格式不符合要求")
    elif ftype == "number":
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            _err(field, "应为数字")
        if "minimum" in schema and val < schema["minimum"]:
            _err(field, f"不能小于 {schema['minimum']}")
        if "maximum" in schema and val > schema["maximum"]:
            _err(field, f"不能大于 {schema['maximum']}")
    elif ftype == "date":
        if not isinstance(val, str) or _DATE_RE.match(val) is None:
            _err(field, "应为 YYYY-MM-DD 日期")
        try:
            dt.date.fromisoformat(val)
        except ValueError:
            _err(field, "日期无效")
    elif ftype == "select":
        if val not in _option_values(field):
            _err(field, "不在可选项内")
    elif ftype in ("multi_select", "checkbox"):
        if not isinstance(val, list):
            _err(field, "应为多选列表")
        opts = _option_values(field)
        for item in val:
            if item not in opts:
                _err(field, "含无效选项")


def validate_values(db: Session, custom_values: dict[str, Any], *, require_check: bool) -> None:
    """校验 custom_values 对当前 active 字段（Q367/Q368）。

    require_check=True 时强制 required；未知键 / 已归档字段键一律容忍（Q255/Q256）。
    """
    fields = list(
        db.execute(
            select(ProcedureField).where(
                ProcedureField.is_active.is_(True), ProcedureField.status == "active"
            )
        ).scalars()
    )
    for field in fields:
        present = field.key in custom_values and not _is_empty(custom_values[field.key])
        if field.required and require_check and not present:
            _err(field, "为必填项，请填写")
        if present:
            _validate_one(field, custom_values[field.key])


# --------------------------------------------------------------------------- #
# CRUD
# --------------------------------------------------------------------------- #
def list_fields(
    db: Session, *, field_type: str | None = None, status: str | None = None
) -> list[ProcedureField]:
    q = select(ProcedureField).where(ProcedureField.is_active.is_(True))
    if field_type:
        q = q.where(ProcedureField.field_type == field_type)
    if status:
        q = q.where(ProcedureField.status == status)
    q = q.order_by(ProcedureField.sort_order, ProcedureField.created_at)
    return list(db.execute(q).scalars())


def options_data(db: Session) -> list[ProcedureField]:
    """active 字段（供 /procedure-fields/options 渲染表单）。"""
    return list_fields(db, status="active")


def active_options(field: ProcedureField) -> list[dict[str, Any]]:
    """过滤 archived 选项（Q255）：archived=True 的选项不暴露给前端。"""
    return [o for o in (field.options or []) if not o.get("archived")]


def get_or_404(db: Session, field_id: str) -> ProcedureField:
    field = db.execute(
        select(ProcedureField).where(
            ProcedureField.id == field_id, ProcedureField.is_active.is_(True)
        )
    ).scalar_one_or_none()
    if field is None:
        raise not_found("NOT_FOUND", "自定义字段不存在")
    return field


def create(db: Session, payload: FieldCreate) -> ProcedureField:
    if KEY_RE.match(payload.key) is None:
        raise unprocessable(
            "VALIDATION_FAILED", "key 须为小写字母开头的字母/数字/下划线", field="key"
        )
    existing = db.execute(
        select(ProcedureField.id).where(ProcedureField.key == payload.key)
    ).first()
    if existing is not None:
        raise conflict("FIELD_KEY_DUPLICATE", "字段 key 已存在", field="key")

    field = ProcedureField(
        name=payload.name,
        key=payload.key,
        field_type=payload.field_type,
        description=payload.description,
        required=payload.required,
        default_value=payload.default_value,
        options=[o.model_dump() for o in payload.options],
        validation_rules=compile_form_to_schema(payload.field_type, payload.validation),
        sort_order=payload.sort_order,
        show_on_cover=payload.show_on_cover,
        status="active",
    )
    db.add(field)
    db.flush()
    return field


def _merge_options(old: list[dict[str, Any]], new: list[FieldOption]) -> list[dict[str, Any]]:
    """options 删除软代理（Q255）：new 中不再出现的旧选项以 archived=True 保留。"""
    new_dicts = [o.model_dump() for o in new]
    new_values = {o["value"] for o in new_dicts}
    result: list[dict[str, Any]] = list(new_dicts)
    for o in old or []:
        if o.get("value") not in new_values:
            result.append({**o, "archived": True})
    return result


def update(db: Session, field_id: str, payload: FieldUpdate) -> ProcedureField:
    field = get_or_404(db, field_id)
    if payload.key is not None and payload.key != field.key:
        raise bad_request("FIELD_KEY_IMMUTABLE", "字段 key 不可修改", field="key")
    if payload.field_type is not None and payload.field_type != field.field_type:
        raise bad_request(
            "FIELD_TYPE_IMMUTABLE", "字段类型不可修改，如需变更请新建字段", field="field_type"
        )
    field.name = payload.name
    field.description = payload.description
    field.required = payload.required
    field.default_value = payload.default_value
    field.options = _merge_options(field.options, payload.options)
    field.validation_rules = compile_form_to_schema(field.field_type, payload.validation)
    field.sort_order = payload.sort_order
    field.show_on_cover = payload.show_on_cover
    db.flush()
    return field


def delete(db: Session, field_id: str) -> None:
    field = get_or_404(db, field_id)
    field.is_active = False
    field.deleted_at = utcnow()
    db.flush()


# --------------------------------------------------------------------------- #
# 批量
# --------------------------------------------------------------------------- #
def _dedup(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def update_status(db: Session, ids: list[str], status: Literal["active", "archived"]) -> list[str]:
    rows = list(
        db.execute(
            select(ProcedureField).where(
                ProcedureField.id.in_(_dedup(ids)), ProcedureField.is_active.is_(True)
            )
        ).scalars()
    )
    for field in rows:
        field.status = status
    db.flush()
    return [f.id for f in rows]


def batch_delete(db: Session, ids: list[str]) -> BatchDeleteResult:
    """原子批量软删（Q325）：先全量校验，任一缺失则全部不动。"""
    unique_ids = _dedup(ids)
    found = {
        f.id: f
        for f in db.execute(
            select(ProcedureField).where(
                ProcedureField.id.in_(unique_ids), ProcedureField.is_active.is_(True)
            )
        ).scalars()
    }
    failed = [
        BatchDeleteFailure(id=i, code="NOT_FOUND", message="自定义字段不存在")
        for i in unique_ids
        if i not in found
    ]
    if failed:
        return BatchDeleteResult(deleted_ids=[], failed=failed)

    now = utcnow()
    for field in found.values():
        field.is_active = False
        field.deleted_at = now
    db.flush()
    return BatchDeleteResult(deleted_ids=list(found.keys()), failed=[])


def reorder(db: Session, ordered_ids: list[str]) -> list[ProcedureField]:
    """按给定顺序重写 sort_order（缺失 id 静默跳过）。返回新顺序的 active 字段。"""
    rows = {
        f.id: f
        for f in db.execute(
            select(ProcedureField).where(
                ProcedureField.id.in_(ordered_ids), ProcedureField.is_active.is_(True)
            )
        ).scalars()
    }
    order = 0
    for fid in ordered_ids:
        field = rows.get(fid)
        if field is not None:
            field.sort_order = order
            order += 1
    db.flush()
    return list_fields(db)
