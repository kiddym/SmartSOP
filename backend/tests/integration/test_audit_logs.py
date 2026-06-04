"""审计日志查询接口集成测试（api-specification §5.9 / Q126-Q127）。"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.audit import FolderAuditLog, ProcedureAuditLog

# 审计行（直建 db）须有 tenant 上下文落 company_id（NOT NULL）；端点本身未鉴权，
# 请求期上下文为 None 不作用域化，故直建行仍可见。
pytestmark = pytest.mark.usefixtures("_tenant_ctx")

FOLDERS_BASE = "/api/v1/audit-logs/folders"
PROCEDURES_BASE = "/api/v1/audit-logs/procedures"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _add_folder_log(
    db: Session,
    *,
    target_id: str = "f1",
    action: str = "create",
    ip_address: str = "1.2.3.4",
    user_agent: str = "pytest",
    old_value: dict | None = None,
    new_value: dict | None = None,
    reason: str = "",
    created_at: datetime | None = None,
) -> FolderAuditLog:
    entry = FolderAuditLog(
        target_id=target_id,
        action=action,
        old_value=old_value or {},
        new_value=new_value or {},
        reason=reason,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    if created_at is not None:
        entry.created_at = created_at
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def _add_procedure_log(
    db: Session,
    *,
    target_id: str = "p1",
    action: str = "create",
    procedure_group_id: str | None = None,
    ip_address: str = "1.2.3.4",
    user_agent: str = "pytest",
    old_value: dict | None = None,
    new_value: dict | None = None,
    reason: str = "",
    created_at: datetime | None = None,
) -> ProcedureAuditLog:
    entry = ProcedureAuditLog(
        target_id=target_id,
        action=action,
        procedure_group_id=procedure_group_id,
        old_value=old_value or {},
        new_value=new_value or {},
        reason=reason,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    if created_at is not None:
        entry.created_at = created_at
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


# ---------------------------------------------------------------------------
# /audit-logs/folders
# ---------------------------------------------------------------------------


def test_folder_audit_empty_list(client: TestClient) -> None:
    """无数据时返回空分页列表。"""
    resp = client.get(FOLDERS_BASE)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert body["items"] == []


def test_folder_audit_basic_pagination(client: TestClient, db: Session) -> None:
    """有数据时返回正确的分页结构。"""
    _add_folder_log(db, target_id="fa1", action="create")
    _add_folder_log(db, target_id="fa2", action="update")
    _add_folder_log(db, target_id="fa3", action="delete")

    resp = client.get(FOLDERS_BASE, params={"page": 1, "page_size": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["items"]) == 2


def test_folder_audit_page_2(client: TestClient, db: Session) -> None:
    """第 2 页只返回剩余 1 条。"""
    for i in range(3):
        _add_folder_log(db, target_id=f"fx{i}", action="create")

    resp = client.get(FOLDERS_BASE, params={"page": 2, "page_size": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 1


def test_folder_audit_filter_target_id(client: TestClient, db: Session) -> None:
    """按 target_id 过滤。"""
    _add_folder_log(db, target_id="match", action="create")
    _add_folder_log(db, target_id="other", action="create")

    resp = client.get(FOLDERS_BASE, params={"target_id": "match"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["target_id"] == "match"


def test_folder_audit_filter_single_action(client: TestClient, db: Session) -> None:
    """按单个 action 过滤。"""
    _add_folder_log(db, target_id="f1", action="create")
    _add_folder_log(db, target_id="f2", action="update")
    _add_folder_log(db, target_id="f3", action="delete")

    resp = client.get(FOLDERS_BASE, params={"action": "create"})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["action"] == "create"


def test_folder_audit_filter_multi_action(client: TestClient, db: Session) -> None:
    """按逗号分隔多个 action 过滤。"""
    _add_folder_log(db, target_id="f1", action="create")
    _add_folder_log(db, target_id="f2", action="update")
    _add_folder_log(db, target_id="f3", action="delete")

    resp = client.get(FOLDERS_BASE, params={"action": "create,update"})
    body = resp.json()
    assert body["total"] == 2
    actions = {item["action"] for item in body["items"]}
    assert actions == {"create", "update"}


def test_folder_audit_filter_date_from(client: TestClient, db: Session) -> None:
    """date_from 过滤：只返回该时间点之后的记录。"""
    base = datetime(2026, 1, 1, 0, 0, 0)
    _add_folder_log(db, target_id="old", action="create", created_at=base)
    _add_folder_log(db, target_id="new", action="update", created_at=base + timedelta(days=1))

    resp = client.get(FOLDERS_BASE, params={"date_from": (base + timedelta(hours=1)).isoformat()})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["target_id"] == "new"


def test_folder_audit_filter_date_to(client: TestClient, db: Session) -> None:
    """date_to 过滤：只返回该时间点之前的记录。"""
    base = datetime(2026, 1, 1, 0, 0, 0)
    _add_folder_log(db, target_id="early", action="create", created_at=base)
    _add_folder_log(db, target_id="late", action="update", created_at=base + timedelta(days=2))

    resp = client.get(
        FOLDERS_BASE,
        params={"date_to": (base + timedelta(hours=1)).isoformat()},
    )
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["target_id"] == "early"


def test_folder_audit_filter_ip_address(client: TestClient, db: Session) -> None:
    """按 ip_address 精确匹配过滤。"""
    _add_folder_log(db, target_id="f1", action="create", ip_address="10.0.0.1")
    _add_folder_log(db, target_id="f2", action="create", ip_address="10.0.0.2")

    resp = client.get(FOLDERS_BASE, params={"ip_address": "10.0.0.1"})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["ip_address"] == "10.0.0.1"


def test_folder_audit_response_shape(client: TestClient, db: Session) -> None:
    """返回的单条记录包含所有必需字段。"""
    _add_folder_log(
        db,
        target_id="shape-test",
        action="create",
        old_value={"x": 1},
        new_value={"x": 2},
        reason="test reason",
        ip_address="5.5.5.5",
        user_agent="test-agent/1.0",
    )
    resp = client.get(FOLDERS_BASE)
    item = resp.json()["items"][0]
    assert "id" in item
    assert item["target_id"] == "shape-test"
    assert item["action"] == "create"
    assert item["old_value"] == {"x": 1}
    assert item["new_value"] == {"x": 2}
    assert item["reason"] == "test reason"
    assert item["ip_address"] == "5.5.5.5"
    assert item["user_agent"] == "test-agent/1.0"
    assert "created_at" in item


def test_folder_audit_export_csv(client: TestClient, db: Session) -> None:
    """export=csv 返回 CSV 文件响应。"""
    _add_folder_log(db, target_id="csv-f1", action="create")
    _add_folder_log(db, target_id="csv-f2", action="update")

    resp = client.get(FOLDERS_BASE, params={"export": "csv"})
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "audit_folders.csv" in resp.headers["content-disposition"]

    # 解析 CSV 内容（跳过 BOM）
    content = resp.content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    assert len(rows) == 2
    target_ids = {r["target_id"] for r in rows}
    assert target_ids == {"csv-f1", "csv-f2"}


def test_folder_audit_export_csv_ascending_order(client: TestClient, db: Session) -> None:
    """CSV 导出按 created_at 升序排列。"""
    base = datetime(2026, 3, 1, 0, 0, 0)
    _add_folder_log(db, target_id="z", action="create", created_at=base + timedelta(hours=2))
    _add_folder_log(db, target_id="a", action="create", created_at=base)

    resp = client.get(FOLDERS_BASE, params={"export": "csv"})
    content = resp.content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    assert rows[0]["target_id"] == "a"
    assert rows[1]["target_id"] == "z"


def test_folder_audit_export_csv_ignores_pagination(client: TestClient, db: Session) -> None:
    """CSV 导出忽略 page / page_size，返回全量。"""
    for i in range(5):
        _add_folder_log(db, target_id=f"all{i}", action="create")

    resp = client.get(FOLDERS_BASE, params={"export": "csv", "page": 1, "page_size": 2})
    content = resp.content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    assert len(rows) == 5


def test_folder_audit_page_size_max_200(client: TestClient, db: Session) -> None:
    """page_size 最大 200，超过返回 422。"""
    resp = client.get(FOLDERS_BASE, params={"page_size": 201})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# /audit-logs/procedures
# ---------------------------------------------------------------------------


def test_procedure_audit_empty_list(client: TestClient) -> None:
    """无数据时返回空列表。"""
    resp = client.get(PROCEDURES_BASE)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []


def test_procedure_audit_basic_data(client: TestClient, db: Session) -> None:
    """有数据时返回正确的分页结构，含 procedure_group_id。"""
    _add_procedure_log(db, target_id="p1", action="create", procedure_group_id="g1")
    _add_procedure_log(db, target_id="p2", action="update", procedure_group_id="g1")

    resp = client.get(PROCEDURES_BASE)
    body = resp.json()
    assert body["total"] == 2
    for item in body["items"]:
        assert "procedure_group_id" in item


def test_procedure_audit_filter_group_id(client: TestClient, db: Session) -> None:
    """按 procedure_group_id 过滤（Q127 跨版本历史）。"""
    _add_procedure_log(db, target_id="p1", action="create", procedure_group_id="grp-A")
    _add_procedure_log(db, target_id="p2", action="update", procedure_group_id="grp-A")
    _add_procedure_log(db, target_id="p3", action="create", procedure_group_id="grp-B")

    resp = client.get(PROCEDURES_BASE, params={"procedure_group_id": "grp-A"})
    body = resp.json()
    assert body["total"] == 2
    for item in body["items"]:
        assert item["procedure_group_id"] == "grp-A"


def test_procedure_audit_filter_target_id(client: TestClient, db: Session) -> None:
    """按 target_id 过滤。"""
    _add_procedure_log(db, target_id="pmatch", action="create")
    _add_procedure_log(db, target_id="pother", action="create")

    resp = client.get(PROCEDURES_BASE, params={"target_id": "pmatch"})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["target_id"] == "pmatch"


def test_procedure_audit_filter_multi_action(client: TestClient, db: Session) -> None:
    """按逗号分隔多 action 过滤。"""
    _add_procedure_log(db, target_id="p1", action="create")
    _add_procedure_log(db, target_id="p2", action="approve")
    _add_procedure_log(db, target_id="p3", action="delete")

    resp = client.get(PROCEDURES_BASE, params={"action": "create,approve"})
    body = resp.json()
    assert body["total"] == 2


def test_procedure_audit_filter_ip(client: TestClient, db: Session) -> None:
    """按 ip_address 过滤。"""
    _add_procedure_log(db, target_id="p1", action="create", ip_address="9.9.9.9")
    _add_procedure_log(db, target_id="p2", action="create", ip_address="8.8.8.8")

    resp = client.get(PROCEDURES_BASE, params={"ip_address": "9.9.9.9"})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["ip_address"] == "9.9.9.9"


def test_procedure_audit_export_csv(client: TestClient, db: Session) -> None:
    """export=csv 返回包含 procedure_group_id 列的 CSV。"""
    _add_procedure_log(db, target_id="exp-p1", action="create", procedure_group_id="grp-csv")

    resp = client.get(PROCEDURES_BASE, params={"export": "csv"})
    assert resp.status_code == 200
    assert "audit_procedures.csv" in resp.headers["content-disposition"]

    content = resp.content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["procedure_group_id"] == "grp-csv"
    assert rows[0]["target_id"] == "exp-p1"


def test_procedure_audit_pagination(client: TestClient, db: Session) -> None:
    """分页参数正确工作。"""
    for i in range(5):
        _add_procedure_log(db, target_id=f"pp{i}", action="create")

    resp = client.get(PROCEDURES_BASE, params={"page": 1, "page_size": 3})
    body = resp.json()
    assert body["total"] == 5
    assert len(body["items"]) == 3

    resp2 = client.get(PROCEDURES_BASE, params={"page": 2, "page_size": 3})
    body2 = resp2.json()
    assert len(body2["items"]) == 2


def test_procedure_audit_date_from_filter(client: TestClient, db: Session) -> None:
    """date_from 过滤程序审计日志。"""
    base = datetime(2026, 4, 1, 0, 0, 0)
    _add_procedure_log(db, target_id="pold", action="create", created_at=base)
    _add_procedure_log(db, target_id="pnew", action="update", created_at=base + timedelta(days=1))

    resp = client.get(
        PROCEDURES_BASE,
        params={"date_from": (base + timedelta(hours=12)).isoformat()},
    )
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["target_id"] == "pnew"
