"""version_service 单测（testing-standards §6.4）。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.services import version_service
from tests.conftest import Factory

pytestmark = pytest.mark.usefixtures("_tenant_ctx")


def test_record_create_appends_single_create_entry(db, factory: Factory) -> None:
    """create 时 version_change_log 含 1 条 change_type=create。"""
    folder = factory.folder(prefix="QC")
    proc = factory.procedure(folder.id)

    version_service.record_create(proc, description="初始创建")
    db.commit()

    assert len(proc.version_change_log) == 1
    entry = proc.version_change_log[0]
    assert entry["change_type"] == "create"
    assert entry["version"] == 1
    assert entry["description"] == "初始创建"
    assert "changed_at" in entry


def test_record_change_does_not_change_version(db, factory: Factory) -> None:
    """记录变更日志本身不改 version。"""
    folder = factory.folder(prefix="QC")
    proc = factory.procedure(folder.id, version=2)

    version_service.record_change(proc, "update", description="改了点东西")
    db.commit()

    assert proc.version == 2
    assert proc.version_change_log[-1]["change_type"] == "update"


def test_record_change_with_reason_and_rollback_from(db, factory: Factory) -> None:
    """rollback 类条目带 reason 与 rollback_from_version。"""
    folder = factory.folder(prefix="QC")
    proc = factory.procedure(folder.id, version=3)

    version_service.record_change(
        proc, "rollback", description="回退", reason="发现错误", rollback_from_version=5
    )

    entry = proc.version_change_log[-1]
    assert entry["reason"] == "发现错误"
    assert entry["rollback_from_version"] == 5


def test_next_version_number(db, factory: Factory) -> None:
    folder = factory.folder(prefix="QC")
    proc = factory.procedure(folder.id, version=4)
    assert version_service.next_version_number(proc) == 5


def test_assert_can_upgrade_passes_below_max(db, factory: Factory) -> None:
    folder = factory.folder(prefix="QC")
    proc = factory.procedure(folder.id, version=4)
    settings = factory.settings(max_version_number=100)

    version_service.assert_can_upgrade(proc, settings)  # 不抛


def test_assert_can_upgrade_raises_at_max(db, factory: Factory) -> None:
    """达到 max_version_number 后再 upgrade 抛 PROCEDURE_VERSION_MAX(400)。"""
    folder = factory.folder(prefix="QC")
    proc = factory.procedure(folder.id, version=100)
    settings = factory.settings(max_version_number=100)

    with pytest.raises(HTTPException) as exc:
        version_service.assert_can_upgrade(proc, settings)
    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "PROCEDURE_VERSION_MAX"
