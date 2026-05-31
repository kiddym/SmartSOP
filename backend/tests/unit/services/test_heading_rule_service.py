"""动态标题字典-样式规则服务 + 解析注入接缝单测（方案 M1）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.parser import parse_docx
from app.schemas.heading_rule import HeadingRuleCreate, HeadingRuleUpdate
from app.services import heading_rule_service as svc
from tests.unit.parser._docx_builder import DocxBuilder


def _all_titles(nodes: list) -> list[str]:
    out: list[str] = []
    for n in nodes:
        if n.content_type == "chapter":
            out.append(n.title)
        out.extend(_all_titles(n.children))
    return out


def test_active_style_overrides_filters(db: Session) -> None:
    # active + level≥1 → 计入；candidate / level=null / 软删 → 不计入
    svc.create(db, HeadingRuleCreate(style_name="公司章标题", level=1))
    cand = svc.create(db, HeadingRuleCreate(style_name="待定样式", level=2))
    svc.update(db, cand, HeadingRuleUpdate(status="candidate"))
    svc.create(db, HeadingRuleCreate(style_name="非标题样式", level=0))  # level→null
    db.flush()

    overrides = svc.active_style_overrides(db)
    assert overrides == {"公司章标题": 1}


def test_create_duplicate_rejected(db: Session) -> None:
    svc.create(db, HeadingRuleCreate(style_name="重复样式", level=1))
    db.flush()
    try:
        svc.create(db, HeadingRuleCreate(style_name="重复样式", level=2))
        raise AssertionError("应拒绝重复样式名")
    except Exception as e:  # conflict → HTTPException
        assert "HEADING_RULE_DUPLICATE" in str(getattr(e, "detail", e))


def test_override_makes_unknown_style_a_chapter(db: Session) -> None:
    """端到端接缝：未知自定义样式默认不识别为标题；写入规则后注入即识别。"""
    data = (
        DocxBuilder()
        .styled_heading("范围", "公司专用标题样式")
        .para("适用于全公司。")
        .build()
    )
    # 无规则：自定义样式名不在同义词词典 → 不成章节
    res0 = parse_docx(data, "smart", style_overrides=svc.active_style_overrides(db))
    assert "范围" not in _all_titles(res0.chapters)

    # 写入规则 → active_style_overrides 注入 → 识别为 L1 章节
    svc.create(db, HeadingRuleCreate(style_name="公司专用标题样式", level=1))
    db.flush()
    res1 = parse_docx(data, "smart", style_overrides=svc.active_style_overrides(db))
    assert "范围" in _all_titles(res1.chapters)


def test_delete_soft_removes_from_active(db: Session) -> None:
    rule = svc.create(db, HeadingRuleCreate(style_name="临时样式", level=1))
    db.flush()
    assert svc.active_style_overrides(db) == {"临时样式": 1}
    svc.delete(db, rule)
    db.flush()
    assert svc.active_style_overrides(db) == {}
