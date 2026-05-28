"""Stage 2 — SectionStructurer：IR 块流 → 章节树（§19 / §25 / Q199 / Q206）。

- standard：仅样式标题（Tier1）成章节；任一非样式块→content。
- smart：样式标题（HIGH 免确认）+ 启发式候选（MEDIUM/LOW 标 review）成章节。
- §19：每个非 heading 正文块 → 最近章节的独立 content 子节点（chapter.rich_content 恒空）。
- Q206：含内联图的段落整体保留为一个 content 节点。
- Q343：正文首个标题之前的正文块丢弃 + warning（不建虚拟前言）。
"""

from __future__ import annotations

import uuid

from app.parser import heading_detector as hd
from app.parser import styles as styles_mod
from app.parser.body_start import find_body_start
from app.parser.ir import Block, ImageRef, NormalizedDoc
from app.parser.result import (
    ParsedNode,
    ParseMetadata,
    ParseResult,
    ParseWarning,
)
from app.parser.utils.opc import DocxPackage
from app.parser.validators import template_validator

_MAX_CHAPTER_LEVEL = 3

# headingSource 归一到 api 枚举（override 视作 style）
_SOURCE_MAP = {
    "override": "style",
    "style": "style",
    "synonym": "synonym",
    "outline": "outline",
    "based_on": "based_on",
}


def _new_id() -> str:
    return str(uuid.uuid4())


def _is_empty(block: Block) -> bool:
    return not (block.text.strip() or block.images) and not block.html.strip()


def structure(
    nd: NormalizedDoc,
    *,
    pkg: DocxPackage,
    mode: str,
    synonyms: dict[str, int],
    style_overrides: dict[str, int],
) -> ParseResult:
    blocks = nd.blocks
    stats = hd.compute_doc_stats(blocks)
    style_index = nd.style_index or styles_mod.StyleIndex()

    # 文档已用样式体系（≥1 个样式 heading）→ 信任作者意图，关闭启发式（spec eval r4）
    # 否则署名 list / 表格行号 等非样式段被升 FP。Tier 1 styled 文档 100% 命中已足够。
    has_style_heading = any(b.style_level is not None for b in blocks)

    # smart：预算启发式候选（供 body_start 兜底链第 3 级）
    heuristic_indices: list[int] = []
    if mode == "smart" and not has_style_heading:
        for b in blocks:
            if b.kind != "paragraph" or b.style_level is not None or not b.text.strip():
                continue
            score, _lvl, _ = hd.score_block(b, stats)
            if hd.tier_for(score) in ("medium", "low"):
                heuristic_indices.append(b.source_index)

    body_start_index, detected_by = find_body_start(
        blocks,
        toc_field_end=nd.toc_field_end_index,
        heuristic_heading_indices=heuristic_indices,
    )
    body_blocks = [b for b in blocks if b.source_index >= body_start_index and not b.is_toc_field]

    chapters: list[ParsedNode] = []
    stack: list[tuple[int, ParsedNode]] = []  # (h_level, node)
    warnings: list[ParseWarning] = []
    image_refs: list[ImageRef] = []
    review_required = 0
    image_count = 0
    table_count = 0

    for block in body_blocks:
        if _is_empty(block):
            continue
        head = _classify_heading(
            block,
            mode,
            style_index,
            synonyms,
            style_overrides,
            stats,
            allow_heuristic=not has_style_heading,
        )
        if head is not None:
            raw_level, conf, tier, mark, source = head
            h_level = min(raw_level, _MAX_CHAPTER_LEVEL)
            while stack and stack[-1][0] >= h_level:
                stack.pop()
            parent = stack[-1][1] if stack else None
            tree_level = min((parent.level + 1) if parent else 1, _MAX_CHAPTER_LEVEL)
            node = ParsedNode(
                id=_new_id(),
                title=block.text.strip(),
                level=tree_level,
                content_type="chapter",
                rich_content="",
                confidence=conf,
                confidence_tier=tier,
                mark_status=mark,
                heading_source=source,
            )
            (parent.children if parent else chapters).append(node)
            stack.append((h_level, node))
            if mark == "review":
                review_required += 1
            continue

        # 非标题块 → content 子节点（§19）
        if not stack:  # 首标题之前的正文块：丢弃 + warning（Q343）
            warnings.append(
                ParseWarning(
                    stage="boundary",
                    message=f"正文首个标题之前的内容块已丢弃：{block.text[:20] or '[图片/表格]'}",
                )
            )
            continue
        current = stack[-1][1]
        content_node = ParsedNode(
            id=_new_id(),
            title="",
            level=current.level + 1,
            content_type="content",
            rich_content=block.html,
        )
        current.children.append(content_node)
        image_refs.extend(block.images)
        image_count += len(block.images)
        if block.kind == "table":
            table_count += 1

    detected_patterns = hd.detect_patterns(body_blocks) if mode == "smart" else []

    validation = template_validator.validate(chapters, body_blocks) if mode == "standard" else None

    # 完整性 warning（C001/C002/C003）补到 warnings（smart 模式无 validation 承载）
    if mode == "smart":
        _append_completeness_warnings(body_blocks, nd, warnings)

    # 页眉/页脚/脚注/批注 丢弃告知（always-on，与模式无关）
    _append_discarded_warning(pkg, warnings)

    total_chapters = _count_chapters(chapters)
    metadata = ParseMetadata(
        total_chapters=total_chapters,
        image_count=image_count,
        table_count=table_count,
        body_start_index=body_start_index,
        body_start_detected_by=detected_by,
    )

    return ParseResult(
        metadata=metadata,
        chapters=chapters,
        parse_method=mode,
        detected_patterns=detected_patterns,
        validation=validation,
        warnings=warnings,
        review_required=review_required,
        image_refs=image_refs,
    )


def _classify_heading(
    block: Block,
    mode: str,
    style_index: styles_mod.StyleIndex,
    synonyms: dict[str, int],
    style_overrides: dict[str, int],
    stats: hd.DocStats,
    allow_heuristic: bool = True,
) -> tuple[int, float, str, str, str] | None:
    """返回 ``(raw_level, confidence, tier, mark_status, heading_source)`` 或 None。

    ``allow_heuristic=False`` 时仅样式 heading 命中（eval r4：已有样式体系的文档
    不需启发式兜底，避免署名 list / 表格行号等被升 FP）。
    """
    if block.kind != "paragraph":
        return None
    # 样式标题（Tier1）→ HIGH 免确认
    if block.style_level is not None:
        _level, src = styles_mod.classify_with_source(
            block.style_id, style_index, synonyms=synonyms, style_overrides=style_overrides
        )
        source = _SOURCE_MAP.get(src or "style", "style")
        return block.style_level, 1.0, "high", "unmarked", source
    # 启发式（仅 smart 且文档无样式体系）→ MEDIUM 直接升，LOW 仅在有真编号信号（heading kind）时升
    # eval r2 trade-off：电厂/危险源 FPs 是 LOW 纯启发式（短+font 误升），但 02记录/
    # 05人力的真实章节有些恰好 0.45（编号+短，但 single_font 等让分凑不到 0.5）—
    # 必须保留对这类的 LOW 提升。weak_heading（N、）不在 LOW 提升内（避免非粗长段
    # 噪音；它们要升必须靠 bold 把自己推到 MEDIUM）。
    if mode == "smart" and allow_heuristic and block.text.strip():
        score, level, _ = hd.score_block(block, stats)
        tier = hd.tier_for(score)
        if tier == "medium":
            return level, score, tier, "review", "heuristic"
        if tier == "low":
            num = hd.classify_numbering(block.text.strip())
            if num is not None and num.kind == "heading":
                return level, score, tier, "review", "heuristic"
    return None


def _count_chapters(nodes: list[ParsedNode]) -> int:
    total = 0
    for n in nodes:
        if n.content_type == "chapter":
            total += 1
        total += _count_chapters(n.children)
    return total


def _append_discarded_warning(pkg: DocxPackage, warnings: list[ParseWarning]) -> None:
    """若 docx 含非空 header/footer/footnotes/endnotes/comments part，推一条 discarded_by_design warning。"""
    parts = pkg.discarded_parts()
    if not parts:
        return
    # 友好缩写：只列文件名的 tail 部分，逗号连接
    tails = [p[len("word/"):] for p in parts]
    warnings.append(
        ParseWarning(
            stage="discarded_by_design",
            message=f"已忽略 {len(parts)} 处页眉/页脚/脚注/批注：{', '.join(tails)}",
        )
    )


def _append_completeness_warnings(
    body_blocks: list[Block], nd: NormalizedDoc, warnings: list[ParseWarning]
) -> None:
    from app.parser.validators import completeness

    img_ok, raw, ext = completeness.image_count_match(body_blocks)
    if not img_ok:
        warnings.append(
            ParseWarning(stage="completeness", message=f"图片可能遗漏：原始 {raw} / 解析 {ext}")
        )
    tbl_ok, traw, tser = completeness.table_count_match(body_blocks)
    if not tbl_ok:
        warnings.append(
            ParseWarning(stage="completeness", message=f"表格可能遗漏：原始 {traw} / 解析 {tser}")
        )
    p_ok, p_raw, p_kept = completeness.paragraph_count_match(nd)
    if not p_ok:
        warnings.append(
            ParseWarning(
                stage="completeness",
                message=f"段落可能遗漏：原始 {p_raw} / 解析 {p_kept}（保留 {p_kept/p_raw:.1%}）",
            )
        )
