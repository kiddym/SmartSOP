"""执行态步骤附件端点集成测试：round-trip + 租户隔离。

Task 3 of feat/execution-attachments：
  - test_upload_list_delete_step_attachment: 上传/列出/删除 round-trip
  - test_step_attachment_tenant_isolated: B 公司无法看到 A 公司的步骤附件
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import tenant
from app.models.node import ProcedureNode
from app.models.procedure import Procedure
from app.models.user import User
from app.schemas.work_order import WorkOrderCreate
from app.services import work_order_execution_service as exe
from app.services import work_order_service as wos

ATT = "/api/v1/attachments"


def _admin(client: TestClient, company: str = "Acme", email: str = "a@acme.com") -> str:
    """注册新公司管理员，返回 access_token。首注册用户具备全权限。"""
    resp = client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "A"},
    )
    return resp.json()["access_token"]


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _company_id(db: Session, email: str) -> str:
    """通过 bypass 跨租户查用户所属公司 id。"""
    with tenant.bypass_tenant_scope():
        u = db.execute(select(User).where(User.email == email)).scalar_one()
    return u.company_id


def _wo_with_upload_step(db: Session, company_id: str) -> tuple[object, str]:
    """db 级造 PUBLISHED 程序(1 个 UPLOAD step) + 工单 + attach_procedure。

    返回 (work_order, step_result_id)。attach_procedure 即刻生成 step_result，
    无需转 IN_PROGRESS 即可对 step_result 上传附件。
    """
    p = Procedure(
        procedure_group_id="grp-t3",
        folder_id="f1",
        code="SOP-T3",
        name="上传测试程序",
        version=1,
        level_of_use="reference",
        status="PUBLISHED",
        company_id=company_id,
    )
    db.add(p)
    db.flush()

    step = ProcedureNode(
        procedure_id=p.id,
        sort_order=1,
        heading_level=None,
        kind="step",
        body="上传图纸",
        code="S1",
        input_schema={"type": "UPLOAD", "required": True},
        company_id=company_id,
    )
    db.add(step)
    db.commit()

    wo = wos.create_work_order(db, WorkOrderCreate(title="T3 工单"), company_id, actor_user_id=None)
    exe.attach_procedure(db, wo, p.id, company_id, actor_user_id=None)
    sr_id = exe.list_step_results(db, wo.id)[0].id
    return wo, sr_id


def test_upload_list_delete_step_attachment(
    client: TestClient, db: Session, storage_tmp: Path
) -> None:
    """上传→列出→删除→确认为空：完整 round-trip。"""
    tok = _admin(client)
    h = _h(tok)
    cid = _company_id(db, "a@acme.com")

    with tenant.bypass_tenant_scope():
        tenant.set_current_company_id(cid)
        _wo, sr_id = _wo_with_upload_step(db, cid)
        tenant.set_current_company_id(None)

    # 上传
    r = client.post(
        ATT,
        headers=h,
        files={"file": ("x.png", b"\x89PNG", "image/png")},
        data={"entity_type": "work_order_step_result", "entity_id": sr_id},
    )
    assert r.status_code == 201, r.text
    att_id = r.json()["id"]
    assert r.json()["entity_type"] == "work_order_step_result"
    assert r.json()["entity_id"] == sr_id

    # 列出
    lst = client.get(
        ATT,
        headers=h,
        params={"entity_type": "work_order_step_result", "entity_id": sr_id},
    )
    assert lst.status_code == 200
    assert [a["id"] for a in lst.json()] == [att_id]

    # 删除
    assert client.delete(f"{ATT}/{att_id}", headers=h).status_code == 204

    # 确认为空
    after = client.get(
        ATT,
        headers=h,
        params={"entity_type": "work_order_step_result", "entity_id": sr_id},
    )
    assert after.json() == []


def test_step_attachment_tenant_isolated(
    client: TestClient, db: Session, storage_tmp: Path
) -> None:
    """B 公司无法看到 A 公司的 step_result（宿主跨租户 → 404）。"""
    tokA = _admin(client, "CoA", "a@a.com")
    tokB = _admin(client, "CoB", "b@b.com")
    hA = _h(tokA)
    hB = _h(tokB)

    cidA = _company_id(db, "a@a.com")

    with tenant.bypass_tenant_scope():
        tenant.set_current_company_id(cidA)
        _wo, sr_id = _wo_with_upload_step(db, cidA)
        tenant.set_current_company_id(None)

    # A 上传
    up = client.post(
        ATT,
        headers=hA,
        files={"file": ("x.png", b"\x89PNG", "image/png")},
        data={"entity_type": "work_order_step_result", "entity_id": sr_id},
    )
    assert up.status_code == 201, up.text

    # B 公司 GET：宿主 step_result 属 A，在 B 的租户作用域下查不到 → 404
    rb = client.get(
        ATT,
        headers=hB,
        params={"entity_type": "work_order_step_result", "entity_id": sr_id},
    )
    assert rb.status_code == 404
