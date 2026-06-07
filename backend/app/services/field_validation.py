"""共享自定义字段值校验。

不依赖具体 ORM 模型——只要字段定义对象有 key/name/field_type/validation_rules/
options 属性即可（ProcedureField 满足该协议；后续 CustomFieldDef（Task 2）亦将满足）。
未知键容忍（不报错）；required 仅在 require_check=True 时强制。
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Sequence
from typing import Any, NoReturn, Protocol

from app.errors import unprocessable

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class FieldDef(Protocol):
    key: str
    name: str
    field_type: str
    required: bool
    validation_rules: dict[str, Any]
    options: list[dict[str, Any]]


def _is_empty(val: Any) -> bool:
    return val is None or val == "" or val == []


def _err(field: FieldDef, msg: str) -> NoReturn:
    raise unprocessable("CUSTOM_FIELD_INVALID", f"字段「{field.name}」{msg}", field=field.key)


def _option_values(field: FieldDef) -> set[str]:
    # active 与 archived 选项值均放行（旧值保留只读，Q255）。
    return {str(o.get("value")) for o in (field.options or [])}


def validate_one(field: FieldDef, val: Any) -> None:
    """校验单个字段值（已知 present）；通常经 validate_against_definitions 调用，也可单独用于单字段实时校验。"""
    schema = field.validation_rules or {}
    ftype = field.field_type
    if ftype in ("text", "textarea"):
        if not isinstance(val, str):
            _err(field, "应为文本")
        if "minLength" in schema and len(val) < schema["minLength"]:
            _err(field, f"长度不足 {schema['minLength']}")
        if "maxLength" in schema and len(val) > schema["maxLength"]:
            _err(field, f"长度超过 {schema['maxLength']}")
        if "pattern" in schema and re.search(schema["pattern"], val) is None:
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


def validate_against_definitions(
    fields: Sequence[FieldDef], custom_values: dict[str, Any], *, require_check: bool
) -> None:
    """校验 custom_values 对字段定义列表（duck-typed，Q367/Q368）。

    require_check=True 时强制 required；未知键 / 已归档字段键一律容忍（Q255/Q256）。
    """
    for field in fields:
        present = field.key in custom_values and not _is_empty(custom_values[field.key])
        if field.required and require_check and not present:
            _err(field, "为必填项，请填写")
        if present:
            validate_one(field, custom_values[field.key])
