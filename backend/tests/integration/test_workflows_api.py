"""工作流引擎与 CRUD：/api/v1/workflows + 工单触发副作用。

覆盖：
- CRUD（创建/列表/改/删）+ schema 枚举校验。
- 租户隔离：A 公司看不到 B 公司工作流，且 B 工作流不影响 A 工单。
- 权限：无 workflow.view 403；无 workflow.manage 不能写。
- 引擎：WORK_ORDER_CREATED + condition priority==HIGH + action set_category
  → 建 HIGH 工单自动落分类；不匹配不动作。
- set_status 动作不无限递归。
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("_enterprise_default")

WF = "/api/v1/workflows"
WO = "/api/v1/work-orders"
CAT = "/api/v1/work-order-categories"


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _mk_category(client, h, name="自动分类"):
    r = client.post(CAT, headers=h, json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _mk_wo(client, h, title, *, priority=None):
    body: dict[str, object] = {"title": title}
    if priority is not None:
        body["priority"] = priority
    r = client.post(WO, headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


# --- CRUD ---


def test_workflow_crud(client):
    h = _h(_admin(client))
    create = client.post(
        WF,
        headers=h,
        json={
            "name": "高优先自动分类",
            "trigger": "WORK_ORDER_CREATED",
            "conditions": [{"field": "priority", "op": "eq", "value": "HIGH"}],
            "actions": [{"type": "set_priority", "value": "LOW"}],
        },
    )
    assert create.status_code == 201, create.text
    wf = create.json()
    assert wf["enabled"] is True
    assert wf["trigger"] == "WORK_ORDER_CREATED"
    assert wf["conditions"][0]["field"] == "priority"

    wid = wf["id"]
    lst = client.get(WF, headers=h)
    assert lst.status_code == 200
    assert any(w["id"] == wid for w in lst.json())

    patch = client.patch(WF + f"/{wid}", headers=h, json={"enabled": False, "name": "改名"})
    assert patch.status_code == 200, patch.text
    assert patch.json()["enabled"] is False
    assert patch.json()["name"] == "改名"

    dele = client.delete(WF + f"/{wid}", headers=h)
    assert dele.status_code == 204
    assert client.get(WF + f"/{wid}", headers=h).status_code == 404


def test_workflow_rejects_bad_enum(client):
    h = _h(_admin(client))
    r = client.post(
        WF,
        headers=h,
        json={
            "name": "x",
            "trigger": "NOT_A_TRIGGER",
            "conditions": [],
            "actions": [],
        },
    )
    assert r.status_code == 422
    r2 = client.post(
        WF,
        headers=h,
        json={
            "name": "x",
            "trigger": "WORK_ORDER_CREATED",
            "conditions": [{"field": "bogus", "op": "eq", "value": "1"}],
            "actions": [],
        },
    )
    assert r2.status_code == 422


# --- 权限 ---


def _make_viewer_token(client, admin_h, *, company_slug="acme"):
    """viewer 角色含 workflow.view（.view 类）但不含 workflow.manage。"""
    roles = client.get("/api/v1/roles", headers=admin_h).json()
    viewer = next(r for r in roles if r["code"] == "viewer")
    client.post(
        "/api/v1/users",
        headers=admin_h,
        json={
            "email": "v@acme.com",
            "password": "secret123",
            "name": "V",
            "role_id": viewer["id"],
        },
    )
    return client.post(
        "/api/v1/auth/login",
        json={"company_slug": company_slug, "email": "v@acme.com", "password": "secret123"},
    ).json()["access_token"]


def test_workflow_requires_view_permission(client):
    admin_h = _h(_admin(client))
    roles = client.get("/api/v1/roles", headers=admin_h).json()
    requester = next(r for r in roles if r["code"] == "requester")
    client.post(
        "/api/v1/users",
        headers=admin_h,
        json={
            "email": "req@acme.com",
            "password": "secret123",
            "name": "R",
            "role_id": requester["id"],
        },
    )
    tok = client.post(
        "/api/v1/auth/login",
        json={"company_slug": "acme", "email": "req@acme.com", "password": "secret123"},
    ).json()["access_token"]
    assert client.get(WF, headers=_h(tok)).status_code == 403


def test_workflow_manage_gated(client):
    admin_h = _h(_admin(client))
    viewer_tok = _make_viewer_token(client, admin_h)
    # viewer 能查看
    assert client.get(WF, headers=_h(viewer_tok)).status_code == 200
    # viewer 不能创建（无 workflow.manage）
    r = client.post(
        WF,
        headers=_h(viewer_tok),
        json={"name": "x", "trigger": "WORK_ORDER_CREATED", "conditions": [], "actions": []},
    )
    assert r.status_code == 403


# --- 引擎行为 ---


def test_engine_sets_category_on_high_priority_create(client):
    h = _h(_admin(client))
    cat_id = _mk_category(client, h)
    client.post(
        WF,
        headers=h,
        json={
            "name": "高优先->分类",
            "trigger": "WORK_ORDER_CREATED",
            "conditions": [{"field": "priority", "op": "eq", "value": "HIGH"}],
            "actions": [{"type": "set_category", "value": cat_id}],
        },
    )
    wo = _mk_wo(client, h, "紧急工单", priority="HIGH")
    assert wo["category_id"] == cat_id


def test_engine_no_action_when_condition_unmatched(client):
    h = _h(_admin(client))
    cat_id = _mk_category(client, h)
    client.post(
        WF,
        headers=h,
        json={
            "name": "高优先->分类",
            "trigger": "WORK_ORDER_CREATED",
            "conditions": [{"field": "priority", "op": "eq", "value": "HIGH"}],
            "actions": [{"type": "set_category", "value": cat_id}],
        },
    )
    wo = _mk_wo(client, h, "普通工单", priority="LOW")
    assert wo["category_id"] is None


def test_engine_disabled_workflow_skipped(client):
    h = _h(_admin(client))
    cat_id = _mk_category(client, h)
    wf = client.post(
        WF,
        headers=h,
        json={
            "name": "停用",
            "enabled": False,
            "trigger": "WORK_ORDER_CREATED",
            "conditions": [],
            "actions": [{"type": "set_category", "value": cat_id}],
        },
    ).json()
    assert wf["enabled"] is False
    wo = _mk_wo(client, h, "工单", priority="HIGH")
    assert wo["category_id"] is None


def test_engine_set_status_no_infinite_recursion(client):
    """status_changed 工作流的 set_status 不应再触发自身导致递归/挂死。"""
    h = _h(_admin(client))
    # 进入 IN_PROGRESS 时自动跳 ON_HOLD（IN_PROGRESS->ON_HOLD 合法）。
    client.post(
        WF,
        headers=h,
        json={
            "name": "进行中即挂起",
            "trigger": "WORK_ORDER_STATUS_CHANGED",
            "conditions": [{"field": "status", "op": "eq", "value": "IN_PROGRESS"}],
            "actions": [{"type": "set_status", "value": "ON_HOLD"}],
        },
    )
    wo = _mk_wo(client, h, "递归测试")
    r = client.post(WO + f"/{wo['id']}/transition", headers=h, json={"to_status": "IN_PROGRESS"})
    assert r.status_code == 200, r.text
    # 引擎把状态推到 ON_HOLD，且没有无限递归（请求正常返回）。
    assert r.json()["status"] == "ON_HOLD"


def test_engine_set_assignee_user(client):
    h = _h(_admin(client))
    # 取当前 admin 用户 id 作为指派目标。
    me = client.get("/api/v1/auth/me", headers=h).json()
    uid = me["id"]
    client.post(
        WF,
        headers=h,
        json={
            "name": "自动指派",
            "trigger": "WORK_ORDER_CREATED",
            "conditions": [],
            "actions": [{"type": "set_assignee_user", "value": uid}],
        },
    )
    wo = _mk_wo(client, h, "工单")
    assert uid in wo["assignee_ids"]


# --- 跨租户 ---


def test_workflow_tenant_isolated_listing(client):
    ha = _h(_admin(client, company="Acme", email="a@acme.com"))
    hb = _h(_admin(client, company="Beta", email="b@beta.com"))
    a_wf = client.post(
        WF,
        headers=ha,
        json={"name": "AcmeWF", "trigger": "WORK_ORDER_CREATED", "conditions": [], "actions": []},
    ).json()
    # B 看不到 A 的工作流
    b_list = client.get(WF, headers=hb).json()
    assert all(w["id"] != a_wf["id"] for w in b_list)
    # B 无法读 A 的工作流详情
    assert client.get(WF + f"/{a_wf['id']}", headers=hb).status_code == 404


def test_cross_tenant_workflow_does_not_affect_other_company_wo(client):
    ha = _h(_admin(client, company="Acme", email="a2@acme.com"))
    hb = _h(_admin(client, company="Beta", email="b2@beta.com"))
    # A 的分类 + A 的工作流（HIGH -> set_category A 分类）
    a_cat = _mk_category(client, ha, name="A分类")
    client.post(
        WF,
        headers=ha,
        json={
            "name": "A高优先->A分类",
            "trigger": "WORK_ORDER_CREATED",
            "conditions": [{"field": "priority", "op": "eq", "value": "HIGH"}],
            "actions": [{"type": "set_category", "value": a_cat}],
        },
    )
    # B 建 HIGH 工单：不应被 A 的工作流影响
    b_wo = _mk_wo(client, hb, "B紧急", priority="HIGH")
    assert b_wo["category_id"] is None
