"""动态标题字典-编号体例服务 + 解析注入接缝单测（方案 M4b）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.parser import parse_docx
from app.schemas.numbering_profile import NumberingProfileCreate, NumberingProfileUpdate
from app.services import numbering_profile_service as svc
from tests.unit.parser._docx_builder import DocxBuilder


def _count_chapters(nodes: list) -> int:
    n = 0
    for x in nodes:
        if x.content_type == "chapter":
            n += 1
        n += _count_chapters(x.children)
    return n


def test_active_numbering_overrides_filters(db: Session) -> None:
    svc.create(db, NumberingProfileCreate(pattern_key="第X条", kind="heading", level=3))
    cand = svc.create(db, NumberingProfileCreate(pattern_key="N.N、", kind="heading", level=2))
    svc.update(db, cand, NumberingProfileUpdate(status="candidate"))
    db.flush()
    assert svc.active_numbering_overrides(db) == {"第X条": ("heading", 3)}


def test_create_rejects_bad_kind(db: Session) -> None:
    try:
        svc.create(db, NumberingProfileCreate(pattern_key="第X条", kind="bogus"))
        raise AssertionError("应拒绝非法 kind")
    except Exception as e:
        assert "NUMBERING_PROFILE_BAD_KIND" in str(getattr(e, "detail", e))


def test_profile_promotes_numbering_via_parse(db: Session) -> None:
    """端到端接缝：『第X条』内置判 weak（非粗不升）；配 heading 体例后被识别为章节。"""
    data = (
        DocxBuilder()
        .para("第一条 目的")
        .para("本程序的目的说明。")
        .para("第二条 范围")
        .para("适用范围说明。")
        .para("第三条 职责")
        .para("职责说明。")
        .build()
    )
    # 无体例：第X条 内置 weak_heading + 非粗 → 不升 → 零章节
    res0 = parse_docx(data, "smart", numbering_overrides=svc.active_numbering_overrides(db))
    assert _count_chapters(res0.chapters) == 0

    # 配体例：第X条 → heading L3 → 三条均被识别为章节
    svc.create(db, NumberingProfileCreate(pattern_key="第X条", kind="heading", level=3))
    db.flush()
    res1 = parse_docx(data, "smart", numbering_overrides=svc.active_numbering_overrides(db))
    assert _count_chapters(res1.chapters) == 3


def test_profile_suppresses_numbering_via_parse(db: Session) -> None:
    """压制：把 N.N、（内置 heading）配成 list → 不再识别为子节。"""
    data = (
        DocxBuilder()
        .para("1、目的", bold=True)
        .para("说明。")
        .para("5.1、顾客沟通")
        .para("内容。")
        .build()
    )
    base = _count_chapters(parse_docx(data, "smart").chapters)
    svc.create(db, NumberingProfileCreate(pattern_key="N.N、", kind="list"))
    db.flush()
    suppressed = _count_chapters(
        parse_docx(data, "smart", numbering_overrides=svc.active_numbering_overrides(db)).chapters
    )
    assert suppressed < base  # 5.1、顾客沟通 被压制，不再成章节
