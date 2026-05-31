"""numbering-profiles REST CRUD（P1d）。"""
from __future__ import annotations

from app.parser.heading_detector import classify_numbering
from app.schemas.numbering_profile import NumberingProfileCreate
from app.services import numbering_profile_service


def test_crud_flow(client) -> None:
    r = client.post("/api/v1/numbering-profiles",
                    json={"pattern_key": "第X条", "kind": "heading", "level": 3})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]

    r = client.get("/api/v1/numbering-profiles")
    assert any(x["pattern_key"] == "第X条" for x in r.json())

    r = client.put(f"/api/v1/numbering-profiles/{pid}", json={"level": 2})
    assert r.status_code == 200 and r.json()["level"] == 2

    r = client.delete(f"/api/v1/numbering-profiles/{pid}")
    assert r.status_code == 204


def test_bad_kind_returns_409(client) -> None:
    r = client.post("/api/v1/numbering-profiles",
                    json={"pattern_key": "X", "kind": "bogus", "level": 1})
    assert r.status_code == 409, r.text


def test_override_upgrades_numbering_kind(db) -> None:
    # 默认「第X条」为 weak_heading；配 profile 覆盖为 heading L3
    numbering_profile_service.create(
        db, NumberingProfileCreate(pattern_key="第X条", kind="heading", level=3)
    )
    db.flush()
    overrides = numbering_profile_service.active_numbering_overrides(db)
    assert overrides["第X条"] == ("heading", 3)
    # classify_numbering 命中 profile → 返回覆盖后的 kind/level
    m = classify_numbering("第三条 适用范围", overrides)
    assert m is not None and m.kind == "heading" and m.level == 3
