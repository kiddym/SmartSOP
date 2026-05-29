"""自定义字段值校验接线单测（Q367/Q368）。

保存路径（create / update / 编辑器整批保存）只校验**已填值的格式**（require_check=False，
草稿可缺必填）；发布（transition→PUBLISHED）才强制必填（require_check=True）。
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.models.field import ProcedureField
from app.models.folder import Folder
from app.schemas.procedure import (
    ProcedureCreate,
    ProcedureUpdate,
    TransitionIn,
)
from app.services import procedure_service
from tests.conftest import Factory

META = RequestMeta(ip_address="203.0.113.9", user_agent="pytest", request_id="r-cf")


def _leaf(factory: Factory) -> Folder:
    folder = factory.folder(name="叶子", prefix="QC", full_path="叶子")
    factory.sequence(folder.id)
    return folder


def _field(
    db: Session,
    *,
    key: str,
    field_type: str = "text",
    required: bool = False,
    validation_rules: dict[str, Any] | None = None,
) -> ProcedureField:
    f = ProcedureField(
        name=key,
        key=key,
        field_type=field_type,
        required=required,
        validation_rules=validation_rules or {},
        options=[],
        status="active",
    )
    db.add(f)
    db.flush()
    return f


def _new(db: Session, leaf_id: str, **values: Any) -> Any:
    return procedure_service.create_procedure(
        db,
        ProcedureCreate(
            folder_id=leaf_id, name="P", level_of_use="continuous", custom_values=values
        ),
        META,  # type: ignore[arg-type]
    )


# --------------------------------------------------------------------------- #
# create：校验已填值格式
# --------------------------------------------------------------------------- #
def test_create_rejects_invalid_present_value(db: Session, factory: Factory) -> None:
    _field(db, key="count", field_type="number")
    leaf = _leaf(factory)
    with pytest.raises(HTTPException) as exc:
        _new(db, leaf.id, count="abc")
    assert exc.value.status_code == 422
    assert exc.value.detail["code"] == "CUSTOM_FIELD_INVALID"


def test_create_allows_missing_required(db: Session, factory: Factory) -> None:
    _field(db, key="owner", required=True)
    leaf = _leaf(factory)
    proc = _new(db, leaf.id)  # 草稿可缺必填
    assert proc.status == "DRAFT"


# --------------------------------------------------------------------------- #
# update：校验已填值格式
# --------------------------------------------------------------------------- #
def test_update_rejects_invalid_present_value(db: Session, factory: Factory) -> None:
    _field(db, key="count", field_type="number")
    leaf = _leaf(factory)
    proc = _new(db, leaf.id)
    with pytest.raises(HTTPException) as exc:
        procedure_service.update_procedure(
            db,
            proc.id,
            ProcedureUpdate(name="P", level_of_use="continuous", custom_values={"count": "abc"}),
            proc.revision,
            META,
        )
    assert exc.value.detail["code"] == "CUSTOM_FIELD_INVALID"


# --------------------------------------------------------------------------- #
# 编辑器整批保存（= update_procedure）：草稿可缺必填
# --------------------------------------------------------------------------- #
def test_update_allows_missing_required(db: Session, factory: Factory) -> None:
    _field(db, key="owner", required=True)
    leaf = _leaf(factory)
    proc = _new(db, leaf.id)
    rev_before = proc.revision
    saved = procedure_service.update_procedure(
        db,
        proc.id,
        ProcedureUpdate(name="P", level_of_use="continuous"),
        rev_before,
        META,
    )
    assert saved.revision == rev_before + 1


# --------------------------------------------------------------------------- #
# 发布：强制必填（require_check=True）
# --------------------------------------------------------------------------- #
def test_publish_rejects_missing_required(db: Session, factory: Factory) -> None:
    _field(db, key="owner", required=True)
    leaf = _leaf(factory)
    proc = _new(db, leaf.id)
    with pytest.raises(HTTPException) as exc:
        procedure_service.transition(
            db, proc.id, TransitionIn(status="PUBLISHED"), proc.revision, META
        )
    assert exc.value.detail["code"] == "CUSTOM_FIELD_INVALID"


def test_publish_allows_when_required_present(db: Session, factory: Factory) -> None:
    _field(db, key="owner", required=True)
    leaf = _leaf(factory)
    proc = _new(db, leaf.id, owner="张三")
    published = procedure_service.transition(
        db, proc.id, TransitionIn(status="PUBLISHED"), proc.revision, META
    )
    assert published.status == "PUBLISHED"
