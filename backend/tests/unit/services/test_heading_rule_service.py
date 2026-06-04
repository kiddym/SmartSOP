"""heading_rule_service 单测（P1b）。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.schemas.heading_rule import HeadingRuleCreate, HeadingRuleUpdate
from app.services import heading_rule_service as svc

pytestmark = pytest.mark.usefixtures("_tenant_ctx")


def test_create_and_active_overrides(db) -> None:
    rule = svc.create(db, HeadingRuleCreate(style_name="章节标题", level=2))
    db.flush()
    assert rule.source == "manual" and rule.status == "active" and rule.level == 2
    assert svc.active_style_overrides(db) == {"章节标题": 2}


def test_level_zero_is_none_and_excluded_from_overrides(db) -> None:
    svc.create(db, HeadingRuleCreate(style_name="正文样式", level=0))
    db.flush()
    # level=0 归一为 None（"非标题"），不进 style_overrides
    assert "正文样式" not in svc.active_style_overrides(db)


def test_duplicate_name_conflicts(db) -> None:
    svc.create(db, HeadingRuleCreate(style_name="重复名", level=1))
    db.flush()
    # 主线 errors.conflict() 返回 HTTPException(409)
    with pytest.raises(HTTPException) as exc:
        svc.create(db, HeadingRuleCreate(style_name="重复名", level=2))
    assert exc.value.status_code == 409


def test_update_pins_to_manual_and_bumps_revision(db) -> None:
    rule = svc.create(db, HeadingRuleCreate(style_name="改级样式", level=1))
    db.flush()
    before = rule.revision
    svc.update(db, rule, HeadingRuleUpdate(level=3))
    assert rule.level == 3 and rule.source == "manual" and rule.revision == before + 1


def test_soft_delete_excludes_from_list_and_overrides(db) -> None:
    rule = svc.create(db, HeadingRuleCreate(style_name="待删", level=1))
    db.flush()
    svc.delete(db, rule)
    db.flush()
    assert all(r.style_name != "待删" for r in svc.list_rules(db))
    assert "待删" not in svc.active_style_overrides(db)
