"""Structurer 单测（M6.2）：§19 章节树 + 置信度 + standard/smart 差异。"""

from __future__ import annotations

from app.parser import normalizer, structurer, synonyms
from app.parser.result import ParseResult
from app.parser.utils.opc import DocxPackage
from tests.unit.parser._docx_builder import (
    DocxBuilder,
    empty_sop,
    styled_sop,
    synonym_sop,
    unstyled_numbered_sop,
)

SYN = synonyms.load_default_synonyms()


def _structure(data: bytes, mode: str) -> ParseResult:
    pkg = DocxPackage(data)
    nd = normalizer.normalize(pkg, synonyms=SYN, style_overrides={})
    return structurer.structure(nd, pkg=pkg, mode=mode, synonyms=SYN, style_overrides={})


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


def test_prose_styled_heading_marked_review() -> None:
    """作者把整句正文误套标题样式 → 解析当章节但标 review（短名词标题仍 unmarked）。"""
    prose = "本试验中使用的气体放射性碘131，需建立临时控制区并设置警示标识。"
    data = (
        DocxBuilder()
        .styled_heading("目的", "章节标题")
        .para("正文一。")
        .styled_heading(prose, "章节标题")
        .para("正文二。")
        .build()
    )
    for mode in ("standard", "smart"):
        res = _structure(data, mode)
        short = next(c for c in _all_nodes(res) if c.title == "目的")
        long_ = next(c for c in _all_nodes(res) if c.title == prose)
        assert short.mark_status == "unmarked", mode
        assert long_.mark_status == "review", mode
        assert long_.confidence_tier == "high"  # 仍信样式，只降确认状态
        assert long_.heading_source in ("style", "synonym")
        assert res.review_required >= 1


def test_standard_validation_fails_without_styled_headings() -> None:
    rep = _structure(unstyled_numbered_sop(), "standard").validation
    assert rep is not None
    assert rep.level == "error"  # H001：无样式标题 → PARSE_TEMPLATE_INVALID


# --------------------------------------------------------------------------- #
# 扁平样式 + 多 numId 混排的跨列表嵌套（P1：_assign_styled_depths）
# --------------------------------------------------------------------------- #
def _styled_blk(i: int, num_id: str | None, ilvl: int | None, level: int = 1) -> object:
    from app.parser.ir import Block

    return Block(
        kind="paragraph",
        source_index=i,
        text=f"标题{i}",
        style_level=level,
        num_id=num_id,
        num_ilvl=ilvl,
    )


def test_assign_styled_depths_nests_foreign_sublist_under_subsection() -> None:
    """扁平样式文档：作者插入的次要子列表（非主大纲 numId，ilvl 从 0 起）若出现在子节内，
    应嵌套为当前 section 的下一级，而非被 per-numId 归一抬回 L1（TP试验程序 numId=11 清单）。"""
    blocks = [
        _styled_blk(0, "1", 1),  # 主大纲 L1（准备）
        _styled_blk(1, "1", 2),  # 主大纲 L2（文件准备）
        _styled_blk(2, "11", 0),  # 次要子列表 → 应 L3（嵌套到 文件准备 之下）
        _styled_blk(3, "11", 0),  # 同列表兄弟 → L3
        _styled_blk(4, "1", 2),  # 回到主大纲 L2（现场准备）
    ]
    num_floor = {"1": 1, "11": 0}
    depths = structurer._assign_styled_depths(blocks, num_floor)
    assert depths[0] == 1
    assert depths[1] == 2
    assert depths[2] == 3  # 次要子列表嵌套加深
    assert depths[3] == 3  # 兄弟同深
    assert depths[4] == 2  # 主大纲不受影响、正确回到 L2


def test_assign_styled_depths_keeps_toplevel_sibling_with_own_numid() -> None:
    """顶层 section 各用独立 numId（ilvl=0）是常见写法 → 仍为 L1 兄弟，不得被误嵌套。"""
    blocks = [
        _styled_blk(0, "2", 0),  # 目的（独立 numId，顶层）
        _styled_blk(1, "6", 0),  # 范围（另一独立 numId，顶层）
    ]
    num_floor = {"2": 0, "6": 0}
    depths = structurer._assign_styled_depths(blocks, num_floor)
    assert depths[0] == 1
    assert depths[1] == 1  # prev_depth==1（顶层）→ 不嵌套


def test_assign_styled_depths_no_op_when_styles_encode_levels() -> None:
    """样式已编码层级（标题1/标题2 混合，非扁平）→ 走基线、不触发跨列表嵌套，规范文档零回归。"""
    blocks = [
        _styled_blk(0, "1", 1, level=1),  # 标题1
        _styled_blk(1, "1", 2, level=2),  # 标题2（样式即 L2）
        _styled_blk(2, "11", 0, level=1),  # 标题1（独立 numId）→ 应保持 L1，不得嵌套
    ]
    num_floor = {"1": 1, "11": 0}
    depths = structurer._assign_styled_depths(blocks, num_floor)
    assert depths[2] == 1  # 非扁平 → 不嵌套，忠实样式层级


def test_content_block_with_placeholder_marked_review() -> None:
    from app.parser.normalizer import normalize
    from app.parser.structurer import structure
    from app.parser.utils.opc import DocxPackage

    data = (
        DocxBuilder()
        .heading("目的", level=1)
        .formula_para(before="计算式")
        .para("普通正文无占位")
        .build()
    )
    pkg = DocxPackage(data)
    nd = normalize(pkg, synonyms={}, style_overrides={})
    result = structure(nd, pkg=pkg, mode="smart", synonyms={}, style_overrides={})
    chapter = result.chapters[0]
    contents = [c for c in chapter.children if c.content_type == "content"]
    ph_node = next(c for c in contents if "sop-ph" in c.rich_content)
    plain_node = next(c for c in contents if "普通正文" in c.rich_content)
    assert ph_node.mark_status == "review"
    assert plain_node.mark_status == "unmarked"
    assert result.review_required >= 1


def test_no_c007_warning_when_placeholders_balanced() -> None:
    from app.parser.normalizer import normalize
    from app.parser.structurer import structure
    from app.parser.utils.opc import DocxPackage

    data = DocxBuilder().heading("目的", level=1).formula_para(before="式").chart_para().build()
    pkg = DocxPackage(data)
    nd = normalize(pkg, synonyms={}, style_overrides={})
    result = structure(nd, pkg=pkg, mode="smart", synonyms={}, style_overrides={})
    ph_warnings = [w for w in result.warnings if "公式/图示" in w.message]
    assert ph_warnings == []  # raw==inserted，不应误报
