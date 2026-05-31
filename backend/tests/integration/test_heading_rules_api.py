"""heading-rules REST CRUD（P1b）。"""
from __future__ import annotations


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
