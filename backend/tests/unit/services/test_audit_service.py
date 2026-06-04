"""audit_service 单测（data-model §3.9 / Q122-Q128）。"""

from __future__ import annotations

import pytest

from app.deps import RequestMeta
from app.models.audit import FolderAuditLog, ProcedureAuditLog
from app.services import audit_service
from tests.conftest import Factory

META = RequestMeta(ip_address="203.0.113.7", user_agent="pytest-UA", request_id="r-1")


pytestmark = pytest.mark.usefixtures("_tenant_ctx")


def test_log_folder_action_persists_with_ip_ua(db, factory: Factory) -> None:
    folder = factory.folder(name="质检")

    audit_service.log_folder_action(
        db, target_id=folder.id, action="create", meta=META, new_value={"name": "质检"}
    )
    db.commit()

    rows = db.query(FolderAuditLog).all()
    assert len(rows) == 1
    assert rows[0].action == "create"
    assert rows[0].ip_address == "203.0.113.7"
    assert rows[0].user_agent == "pytest-UA"
    assert rows[0].new_value == {"name": "质检"}


def test_log_procedure_action_records_group_id(db, factory: Factory) -> None:
    folder = factory.folder(prefix="QC")
    proc = factory.procedure(folder.id)

    audit_service.log_procedure_action(
        db,
        target_id=proc.id,
        procedure_group_id=proc.procedure_group_id,
        action="create",
        meta=META,
    )
    db.commit()

    row = db.query(ProcedureAuditLog).one()
    assert row.procedure_group_id == proc.procedure_group_id
    assert row.target_id == proc.id


def test_log_with_reason(db, factory: Factory) -> None:
    folder = factory.folder(prefix="QC")
    proc = factory.procedure(folder.id)

    audit_service.log_procedure_action(
        db,
        target_id=proc.id,
        procedure_group_id=proc.procedure_group_id,
        action="deprecate",
        meta=META,
        reason="不再适用",
    )
    db.commit()

    assert db.query(ProcedureAuditLog).one().reason == "不再适用"


def test_compute_diff_returns_only_changed_fields() -> None:
    before = {"name": "旧", "prefix": "QC", "system": False}
    after = {"name": "新", "prefix": "QC", "system": False}

    old_value, new_value = audit_service.compute_diff(before, after)

    assert old_value == {"name": "旧"}
    assert new_value == {"name": "新"}


def test_compute_diff_detects_added_keys() -> None:
    old_value, new_value = audit_service.compute_diff({}, {"a": 1})
    assert old_value == {"a": None}
    assert new_value == {"a": 1}


def test_compute_diff_detects_removed_keys() -> None:
    # 被移除的键（before 有、after 无）也应记入 diff
    old_value, new_value = audit_service.compute_diff({"a": 1, "b": 2}, {"a": 1})
    assert old_value == {"b": 2}
    assert new_value == {"b": None}
