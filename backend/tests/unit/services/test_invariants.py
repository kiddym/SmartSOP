"""enforce_content_kind_invariant 单元测试。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.services._invariants import enforce_content_kind_invariant


def test_step_kind_with_any_fields_is_ok() -> None:
    # step kind 不受约束
    enforce_content_kind_invariant("step", {"type": "text"}, [{"id": "a"}])  # no raise


def test_content_kind_with_all_empty_is_ok() -> None:
    enforce_content_kind_invariant("content", {}, [])  # no raise


def test_content_kind_with_none_is_ok() -> None:
    enforce_content_kind_invariant("content", None, None)  # no raise


def test_content_kind_with_non_empty_input_schema_raises() -> None:
    with pytest.raises(HTTPException) as exc:
        enforce_content_kind_invariant("content", {"type": "text"}, [])
    assert exc.value.status_code == 422
    assert "input_schema" in exc.value.detail["message"]


def test_content_kind_with_non_empty_attachment_marks_raises() -> None:
    with pytest.raises(HTTPException) as exc:
        enforce_content_kind_invariant("content", {}, [{"id": "a"}])
    assert exc.value.status_code == 422
    assert "attachment_marks" in exc.value.detail["message"]
