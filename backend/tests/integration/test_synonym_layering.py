"""同义词分层：租户规则 > 平台默认 yaml > 回退默认（P3）。"""
from __future__ import annotations

import pytest

from app import tenant
from app.models.company import Company
from app.parser.styles import StyleIndex, StyleInfo, classify_with_source
from app.parser.synonyms import load_default_synonyms
from app.schemas.heading_rule import HeadingRuleCreate
from app.services import heading_rule_service as svc


@pytest.fixture
def company(db):
    c = Company(name="租户X", slug="tenant-x")
    db.add(c)
    db.flush()
    return c.id


def _index_with(style_name: str) -> StyleIndex:
    idx = StyleIndex()
    idx.by_id["sid"] = StyleInfo(style_id="sid", name=style_name, outline_lvl=None, based_on=None)
    return idx


def test_platform_default_applies_without_tenant_rule() -> None:
    syn = load_default_synonyms()
    style, default_lv = next(iter(syn.items()))
    idx = _index_with(style)
    level, source = classify_with_source("sid", idx, synonyms=syn, style_overrides={})
    assert level == default_lv and source == "synonym"  # 回退平台默认


def test_tenant_rule_overrides_platform_default(db, company) -> None:
    syn = load_default_synonyms()
    style, default_lv = next(iter(syn.items()))
    target = 1 if default_lv != 1 else 2  # 选一个与默认不同的层级
    tenant.set_current_company_id(company)
    svc.create(db, HeadingRuleCreate(style_name=style, level=target))
    db.flush()
    overrides = svc.active_style_overrides(db)  # per-tenant
    idx = _index_with(style)
    level, source = classify_with_source("sid", idx, synonyms=syn, style_overrides=overrides)
    assert level == target and source == "override"  # 租户规则优先于 yaml
