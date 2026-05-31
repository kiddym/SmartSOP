"""heading-rules REST CRUD（P1b）。"""
from __future__ import annotations

from app.parser import parse_docx
from app.parser.eval.accuracy import level_distribution
from app.schemas.heading_rule import HeadingRuleCreate
from app.services import heading_rule_service
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
