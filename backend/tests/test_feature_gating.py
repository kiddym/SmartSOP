"""feature gate 与 RBAC 正交叠加：free 锁高级模块，pro 解锁，super_admin 不绕。"""

import pytest
from sqlalchemy import select

from app.models.company import Company


def _admin(client, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _set_plan(db, *, plan, status="active"):
    company = db.execute(select(Company)).scalars().first()
    company.plan = plan
    company.subscription_status = status
    db.commit()


def test_meters_locked_on_free_returns_402(client):
    t = _admin(client)  # 新公司默认 free
    r = client.get("/api/v1/meters", headers=_h(t))
    assert r.status_code == 402, r.text
    assert r.json()["detail"]["code"] == "FEATURE_LOCKED"


def test_meters_unlocked_on_pro(client, db):
    t = _admin(client)
    _set_plan(db, plan="pro")
    r = client.get("/api/v1/meters", headers=_h(t))
    assert r.status_code == 200, r.text


def test_super_admin_does_not_bypass_feature_gate(client, db):
    # 注册用户即 super_admin（通配权限），但 free 档仍被 feature gate 拦
    t = _admin(client)
    r = client.get("/api/v1/meters", headers=_h(t))
    assert r.status_code == 402, r.text


def test_pro_but_inactive_status_downgrades(client, db):
    t = _admin(client)
    _set_plan(db, plan="pro", status="past_due")
    r = client.get("/api/v1/meters", headers=_h(t))
    assert r.status_code == 402, r.text


# 代表性 GET 端点（仅含已挂闸的「有鉴权」高级模块）。
# 说明：sop 功能对应的 procedures/procedure_groups/nodes/parse/heading_rules/folders/
# batch_imports 这些 router 尚未与认证/多租户整合（无 get_current_user），挂 feature
# gate 会让既有无 token 测试变 401 而非 402，故本轮推迟 sop 挂闸；Feature.sop 仍保留
# 在 catalog 中，待「SOP 接入认证/多租户」后续轮次再挂闸。
_LOCKED_ENDPOINTS = [
    "/api/v1/preventive-maintenances",
    "/api/v1/purchase-orders",
    "/api/v1/analytics/work-orders",
]


@pytest.mark.parametrize("path", _LOCKED_ENDPOINTS)
def test_advanced_endpoints_locked_on_free(client, path):
    t = _admin(client)
    r = client.get(path, headers=_h(t))
    assert r.status_code == 402, f"{path} -> {r.status_code} {r.text}"


@pytest.mark.parametrize("path", _LOCKED_ENDPOINTS)
def test_advanced_endpoints_unlocked_on_pro(client, db, path):
    t = _admin(client)
    _set_plan(db, plan="pro")
    r = client.get(path, headers=_h(t))
    assert r.status_code != 402, f"{path} -> {r.status_code} {r.text}"


def test_core_modules_not_feature_gated(client):
    # 核心模块在 free 档仍可访问（不被 feature gate 拦）
    t = _admin(client)
    for path in ("/api/v1/work-orders", "/api/v1/assets", "/api/v1/locations", "/api/v1/requests"):
        r = client.get(path, headers=_h(t))
        assert r.status_code == 200, f"{path} -> {r.status_code} {r.text}"
