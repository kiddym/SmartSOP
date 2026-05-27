"""Structurer 单测（M6.2）：§19 章节树 + 置信度 + standard/smart 差异。"""

from __future__ import annotations

from app.parser import normalizer, structurer, synonyms
from app.parser.result import ParseResult
from app.parser.utils.opc import DocxPackage
from tests.unit.parser._docx_builder import (
    empty_sop,
    styled_sop,
    synonym_sop,
    unstyled_numbered_sop,
)

SYN = synonyms.load_default_synonyms()


def _structure(data: bytes, mode: str) -> ParseResult:
    nd = normalizer.normalize(DocxPackage(data), synonyms=SYN, style_overrides={})
    return structurer.structure(nd, mode=mode, synonyms=SYN, style_overrides={})


def _all_nodes(result: ParseResult) -> list:
    out = []

    def walk(nodes: list) -> None:
        for n in nodes:
            out.append(n)
            walk(n.children)

    walk(result.chapters)
    return out


def test_styled_standard_builds_chapter_tree() -> None:
    res = _structure(styled_sop(), "standard")
    roots = [c for c in res.chapters if c.content_type == "chapter"]
    titles = [c.title for c in roots]
    assert "目的" in titles
    purpose = next(c for c in res.chapters if c.title == "目的")
    assert purpose.confidence_tier == "high"
    assert purpose.mark_status == "unmarked"
    assert purpose.heading_source == "style"
    assert purpose.rich_content == ""  # §19：chapter 不承载正文


def test_chapter_has_content_child_node() -> None:
    res = _structure(styled_sop(), "standard")
    purpose = next(c for c in res.chapters if c.title == "目的")
    contents = [c for c in purpose.children if c.content_type == "content"]
    assert len(contents) == 1
    assert "本程序规定" in contents[0].rich_content


def test_inline_image_one_content_node() -> None:
    res = _structure(styled_sop(), "standard")
    nodes = _all_nodes(res)
    img_nodes = [n for n in nodes if n.content_type == "content" and "<img" in n.rich_content]
    assert len(img_nodes) == 1  # Q206：文字+图+文字 一个节点
    assert "流程见图" in img_nodes[0].rich_content
    assert "所示。" in img_nodes[0].rich_content


def test_table_becomes_content_node() -> None:
    res = _structure(styled_sop(), "standard")
    nodes = _all_nodes(res)
    tbl_nodes = [n for n in nodes if "<table" in n.rich_content]
    assert len(tbl_nodes) == 1
    assert tbl_nodes[0].content_type == "content"


def test_synonym_standard_detects_headings() -> None:
    res = _structure(synonym_sop(), "standard")
    roots = [c for c in res.chapters if c.content_type == "chapter"]
    assert len(roots) == 2
    assert roots[0].heading_source == "synonym"
    assert roots[0].confidence == 1.0


def test_unstyled_standard_yields_no_chapters() -> None:
    res = _structure(unstyled_numbered_sop(), "standard")
    chapters = [c for c in res.chapters if c.content_type == "chapter"]
    assert chapters == []


def test_unstyled_smart_detects_review_candidates() -> None:
    res = _structure(unstyled_numbered_sop(), "smart")
    chapters = [c for c in _all_nodes(res) if c.content_type == "chapter"]
    assert len(chapters) >= 2  # "1 目的" "2 范围" ...
    assert all(c.mark_status == "review" for c in chapters)
    assert all(c.confidence_tier in ("medium", "low") for c in chapters)
    assert all(c.heading_source == "heuristic" for c in chapters)
    assert res.review_required == len(chapters)


def test_smart_emits_detected_patterns() -> None:
    res = _structure(unstyled_numbered_sop(), "smart")
    assert len(res.detected_patterns) >= 1
    l1 = next(p for p in res.detected_patterns if p.suggested_level == 1)
    assert l1.count >= 2


def test_empty_doc_no_chapters_both_modes() -> None:
    assert [c for c in _structure(empty_sop(), "standard").chapters] == []
    assert [c for c in _structure(empty_sop(), "smart").chapters] == []


def test_metadata_and_body_start() -> None:
    res = _structure(styled_sop(), "standard")
    assert res.metadata.body_start_detected_by == "first_styled_heading"
    assert res.metadata.total_chapters >= 3
    assert res.metadata.image_count >= 1
    assert res.metadata.table_count == 1


def test_standard_validation_report_present_smart_absent() -> None:
    assert _structure(styled_sop(), "standard").validation is not None
    assert _structure(styled_sop(), "smart").validation is None


def test_standard_validation_fails_without_styled_headings() -> None:
    rep = _structure(unstyled_numbered_sop(), "standard").validation
    assert rep is not None
    assert rep.level == "error"  # H001：无样式标题 → PARSE_TEMPLATE_INVALID
