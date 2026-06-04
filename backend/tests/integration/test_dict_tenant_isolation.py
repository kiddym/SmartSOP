"""动态字典多租户隔离 + IDOR 对抗测试（P2）。

依赖主线 tenant_isolation ORM 事件：before_flush 自动盖 company_id、
do_orm_execute 自动给 SELECT 加 company_id 过滤。本测试证明隔离真生效。
conftest 默认清空租户上下文，测试内须显式 tenant.set_current_company_id(...)。
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app import tenant
from app.models.company import Company
from app.schemas.heading_rule import HeadingRuleCreate
from app.services import heading_rule_service as svc


@pytest.fixture
def two_companies(db):
    a = Company(name="A公司", slug="a-co")
    b = Company(name="B公司", slug="b-co")
    db.add_all([a, b])
    db.flush()
    return a.id, b.id


def test_same_style_name_isolated_per_tenant(db, two_companies) -> None:
    a, b = two_companies
    # A 公司：章节标题=1
    tenant.set_current_company_id(a)
    svc.create(db, HeadingRuleCreate(style_name="章节标题", level=1))
    db.flush()
    assert svc.active_style_overrides(db) == {"章节标题": 1}
    # B 公司：同名 章节标题=2（复合唯一允许共存）
    tenant.set_current_company_id(b)
    svc.create(db, HeadingRuleCreate(style_name="章节标题", level=2))
    db.flush()
    assert svc.active_style_overrides(db) == {"章节标题": 2}  # 只见 B 的
    # 回到 A：仍是 1，未被 B 污染
    tenant.set_current_company_id(a)
    assert svc.active_style_overrides(db) == {"章节标题": 1}
    assert len(svc.list_rules(db)) == 1  # A 只见自己一条


def test_cross_tenant_get_returns_404(db, two_companies) -> None:
    a, b = two_companies
    tenant.set_current_company_id(a)
    rule = svc.create(db, HeadingRuleCreate(style_name="A私有", level=1))
    db.flush()
    rid = rule.id
    # B 公司拿 A 的 id → get_or_404 应找不到（do_orm_execute 过滤掉）→ HTTPException(404)
    tenant.set_current_company_id(b)
    with pytest.raises(HTTPException) as exc:
        svc.get_or_404(db, rid)
    assert exc.value.status_code == 404


# ---- Task 4: 投票聚合按租户分区 ---- #
from app.models.node import ProcedureNode  # noqa: E402
from app.services import heading_learning_service as learn  # noqa: E402


def _styled_node(db, pid, level, company_id, style="章节标题"):
    # 主线 node 无 title 列；kind 默认 'node'。先设租户上下文，before_flush 自动盖 company_id。
    tenant.set_current_company_id(company_id)
    n = ProcedureNode(
        procedure_id=pid,
        sort_order=1000,
        heading_level=level,
        mark_status="unmarked",
        source_style_name=style,
        revision=1,
    )
    db.add(n)
    db.flush()
    return n


def test_reaggregate_partitioned_by_tenant(db, two_companies) -> None:
    a, b = two_companies
    # A 公司 3 文档一致把「章节标题」改 L2 → A 规则应 active L2
    for i in range(3):
        node = _styled_node(db, f"a-{i}", 2, a)
        learn.observe_node_edit(db, node, old_level=1, old_mark="unmarked")
    tenant.set_current_company_id(a)
    rule_a = learn.reaggregate(db, "章节标题")
    assert rule_a is not None and rule_a.status == "active" and rule_a.level == 2
    # B 公司：无任何事件 → reaggregate 不应受 A 的事件影响
    tenant.set_current_company_id(b)
    rule_b = learn.reaggregate(db, "章节标题")
    # B 无证据 → 无规则或非 active（绝不继承 A 的 L2）
    assert rule_b is None or rule_b.status != "active" or rule_b.level != 2


# ---- Task 5(P5): API 层可见性隔离（请求级租户 = bearer token 的 company_id）---- #
def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _register(client, *, company, email):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


@pytest.mark.usefixtures("_enterprise_default")
def test_api_list_isolated_per_tenant(client) -> None:
    # A 公司经 API 建规则
    ta = _register(client, company="AcmeDict", email="admin@acmedict.com")
    r = client.post(
        "/api/v1/heading-rules", json={"style_name": "A样式", "level": 1}, headers=_h(ta)
    )
    assert r.status_code == 201, r.text
    # A 自己能看到
    assert any(
        x["style_name"] == "A样式"
        for x in client.get("/api/v1/heading-rules", headers=_h(ta)).json()
    )
    # B 公司 GET 列表看不到 A 的规则（ORM 事件按 token 的 company_id 自动分区）
    tb = _register(client, company="BetaDict", email="admin@betadict.com")
    b_list = client.get("/api/v1/heading-rules", headers=_h(tb)).json()
    assert all(x["style_name"] != "A样式" for x in b_list)
