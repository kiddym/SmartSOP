"""heading-rules REST CRUD（P1b）。"""

from __future__ import annotations

from app.models.node import ProcedureNode
from app.parser import parse_docx
from app.parser.eval.accuracy import level_distribution
from app.schemas.heading_rule import HeadingRuleCreate
from app.services import heading_learning_service, heading_rule_service
from tests.unit.parser._docx_builder import styled_sop


def test_crud_flow(client) -> None:
    # 创建
    r = client.post("/api/v1/heading-rules", json={"style_name": "章节标题", "level": 2})
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    assert r.json()["source"] == "manual" and r.json()["status"] == "active"

    # 列表
    r = client.get("/api/v1/heading-rules")
    assert r.status_code == 200
    assert any(x["style_name"] == "章节标题" for x in r.json())

    # 更新 level
    r = client.put(f"/api/v1/heading-rules/{rid}", json={"level": 3})
    assert r.status_code == 200 and r.json()["level"] == 3

    # 删除
    r = client.delete(f"/api/v1/heading-rules/{rid}")
    assert r.status_code == 204
    r = client.get("/api/v1/heading-rules")
    assert all(x["id"] != rid for x in r.json())


def test_duplicate_returns_409(client) -> None:
    client.post("/api/v1/heading-rules", json={"style_name": "重复", "level": 1})
    r = client.post("/api/v1/heading-rules", json={"style_name": "重复", "level": 2})
    assert r.status_code == 409, r.text


def test_active_overrides_feed_parse_docx(db) -> None:
    # 无规则：active_style_overrides 为空
    assert heading_rule_service.active_style_overrides(db) == {}
    # 建一条 active 规则
    heading_rule_service.create(db, HeadingRuleCreate(style_name="章节标题", level=2))
    db.flush()
    overrides = heading_rule_service.active_style_overrides(db)
    assert overrides == {"章节标题": 2}
    # 把 override 喂进 parse_docx：注入参数被解析链接受（不抛错、产出章节树）
    res = parse_docx(styled_sop(), "standard", style_overrides=overrides)
    assert level_distribution(res.chapters)  # 非空，注入链通


def _styled_node(db, pid: str, level: int, style: str = "章节标题") -> ProcedureNode:
    # 主线 node 无 title 列（标题派生自 body）；kind 默认 'node'。
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


def test_three_docs_consistent_relevel_activates_rule(db) -> None:
    # 3 份文档各有一个「章节标题」节点，用户一致把它改为 L2
    for i in range(3):
        pid = f"proc-{i}"
        node = _styled_node(db, pid, level=1)
        node.heading_level = 2  # 用户改级
        heading_learning_service.observe_node_edit(db, node, old_level=1, old_mark="unmarked")
    rule = heading_learning_service.reaggregate(db, "章节标题")
    assert rule is not None and rule.source == "learned"
    assert rule.status == "active" and rule.level == 2  # ≥3 文档一致 → 自动生效
    # 生效规则进入解析注入
    assert heading_rule_service.active_style_overrides(db).get("章节标题") == 2
