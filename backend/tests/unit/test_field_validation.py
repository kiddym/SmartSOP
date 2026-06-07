"""共享字段值校验（duck-typed 于任意字段定义对象）。"""

from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Any

import pytest
from fastapi import HTTPException

from app.services import field_validation as fv


@dataclass
class FakeDef:
    key: str
    name: str
    field_type: str
    required: bool = False
    validation_rules: dict[str, Any] = dc_field(default_factory=dict)
    options: list[dict[str, Any]] = dc_field(default_factory=list)


def test_text_min_length_violation_raises():
    defs = [FakeDef(key="note", name="备注", field_type="text", validation_rules={"minLength": 3})]
    with pytest.raises(HTTPException):
        fv.validate_against_definitions(defs, {"note": "ab"}, require_check=False)


def test_required_missing_raises_when_require_check():
    defs = [FakeDef(key="note", name="备注", field_type="text", required=True)]
    with pytest.raises(HTTPException):
        fv.validate_against_definitions(defs, {}, require_check=True)


def test_required_missing_ok_when_not_require_check():
    defs = [FakeDef(key="note", name="备注", field_type="text", required=True)]
    fv.validate_against_definitions(defs, {}, require_check=False)  # no raise


def test_select_value_not_in_options_raises():
    defs = [FakeDef(key="c", name="颜色", field_type="select", options=[{"value": "red"}])]
    with pytest.raises(HTTPException):
        fv.validate_against_definitions(defs, {"c": "blue"}, require_check=False)


def test_unknown_key_ignored_by_shared_validator():
    # 共享校验器对未知键容忍（SOP 行为）；未知键拒绝是 CustomField 上层的额外检查。
    defs = [FakeDef(key="note", name="备注", field_type="text")]
    fv.validate_against_definitions(defs, {"ghost": "x"}, require_check=False)  # no raise
