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

# 散文体标题判定（作者把整句正文误套标题样式 → 解析忠实当章节，但提请人工复核）。
# 句读：整句几乎必含逗号/句号/分号/叹问号；纯短名词短语标题极少出现。
_PROSE_PUNCT = "，。；！？,;!?"
_PROSE_LEN_HARD = 40  # 超长标题：纯长度即可疑（真实章节标题罕见 ≥40 字）
_PROSE_LEN_SOFT = 25  # 较长 + 含句读 → 疑似整句

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
    numbering_overrides: dict[str, tuple[str, int | None]] | None = None,
) -> ParseResult:
    blocks = nd.blocks
    stats = hd.compute_doc_stats(blocks, numbering_overrides)
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

    # 样式标题层级细化用：每个 numId 在样式标题中观察到的最小 ilvl（归一基线）。
    # 单一扁平样式（如「章节标题」全 level 1）+ Word 多级编号的文档，真实层级藏在
    # 段落 numPr/ilvl 里；按 numId 归一后用相对深度细化（_refine_styled_level）。
    num_floor: dict[str, int] = {}
    for b in body_blocks:
        if (
            b.style_level is not None
            and b.kind == "paragraph"
            and b.num_id is not None
            and b.num_ilvl is not None
        ):
            prev = num_floor.get(b.num_id)
            num_floor[b.num_id] = b.num_ilvl if prev is None else min(prev, b.num_ilvl)

    # 样式标题层级预计算（含扁平样式 + 多 numId 混排的跨列表嵌套修正，见 _assign_styled_depths）。
    styled_depths = _assign_styled_depths(body_blocks, num_floor)

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
            if block.style_level is not None:  # 样式标题：用预计算层级（段落级 outlineLvl/ilvl 细化）
                raw_level = styled_depths.get(block.source_index, raw_level)
                # 样式标题（默认免确认）若像整句正文 → 改 review，提请复核（不改 tier/source）
                if mark == "unmarked" and _looks_like_prose(block.text.strip()):
                    mark = "review"
            h_level = min(raw_level, _MAX_CHAPTER_LEVEL)
            while stack and stack[-1][0] >= h_level:
                stack.pop()
            parent = stack[-1][1] if stack else None
            tree_level = min((parent.level + 1) if parent else 1, _MAX_CHAPTER_LEVEL)
            src_style_name, src_num_pattern = _attribution(block, style_index, stats)
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
                source_style_name=src_style_name,
                source_numbering_pattern=src_num_pattern,
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
        content_mark = "review" if block.placeholder_count > 0 else "unmarked"
        content_node = ParsedNode(
            id=_new_id(),
            title="",
            level=current.level + 1,
            content_type="content",
            rich_content=block.html,
            mark_status=content_mark,
        )
        current.children.append(content_node)
        if content_mark == "review":
            review_required += 1
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


def _assign_styled_depths(body_blocks: list[Block], num_floor: dict[str, int]) -> dict[int, int]:
    """为样式标题预计算层级，返回 ``{source_index: depth}``（仅含样式标题块）。

    基线为 ``_refine_styled_level``（outline / per-numId floor）。在「扁平样式」文档
    （全部样式标题同一 style_level、层级全靠 Word 多级编号表达）上额外修正一种 per-numId
    归一无法处理的情形：作者插入的**次要子列表**（非主大纲 numId）若出现在某子节
    （深度 ≥ L2）之内，其自身 ilvl 从 0 起算会被归一抬回 L1，割裂嵌套并令其后的主大纲
    标题错挂父节点（TP试验程序：``numId=11`` 的「碘样品分析单…」清单应在「文件准备」(L2)
    之下却被抬到 L1，连带「现场准备」错挂）。这里按文档顺序，把这类次要子列表嵌套到当前
    section 之下。

    仅对扁平样式启用——样式已编码层级的规范文档（标题1/2/3）走基线、零改动、无回归。
    """
    from collections import Counter

    styled = [
        b
        for b in body_blocks
        if b.style_level is not None and b.kind == "paragraph" and b.text.strip()
    ]
    # 扁平样式：所有样式标题同一 style_level（层级信号全在编号里）
    flat = len({b.style_level for b in styled}) <= 1
    # 主大纲 numId：样式标题中出现最多的 numId（None 不计）
    num_counts = Counter(b.num_id for b in styled if b.num_id is not None)
    dominant = num_counts.most_common(1)[0][0] if num_counts else None

    out: dict[int, int] = {}
    prev_num_id: str | None = None
    prev_depth: int | None = None
    for b in styled:
        depth = _refine_styled_level(b, b.style_level or 1, num_floor)
        if flat and b.num_id is not None and b.num_id != dominant and prev_depth is not None:
            if b.num_id == prev_num_id:
                depth = prev_depth  # 同一次要列表内 → 兄弟，沿用上一深度
            elif depth <= prev_depth and prev_depth >= 2:
                # 次要子列表出现在子节（≥L2）之内 → 嵌套为当前 section 的下一级
                depth = min(prev_depth + 1, _MAX_CHAPTER_LEVEL)
        out[b.source_index] = depth
        prev_num_id = b.num_id
        prev_depth = depth
    return out


def _refine_styled_level(block: Block, base_level: int, num_floor: dict[str, int]) -> int:
    """用段落级 outlineLvl / numPr ilvl 细化样式标题层级（修复扁平样式层级压平）。

    ``base_level`` 是样式名/同义词推出的基线层级。当文档用单一扁平样式（所有标题
    同级）却靠 Word 多级编号表达层级时，仅靠样式名会把三级结构压成一级。这里取
    ``max(基线, 段落级深度)``——只能加深、不能变浅，保证规范分级文档（标题1/2/3
    各级 ilvl 与样式一致）不回归（max 为 no-op），而扁平样式文档恢复层级。

    深度信号优先级：段落 outlineLvl（最权威，0-based→1-based）> numPr ilvl（按该
    numId 归一基线 num_floor 取相对深度；跨 numId 的 ilvl 不可直接比，故先归一）。
    """
    depth = base_level
    if block.outline_lvl is not None:
        depth = max(depth, block.outline_lvl + 1)
    elif block.num_id is not None and block.num_ilvl is not None:
        floor = num_floor.get(block.num_id, block.num_ilvl)
        depth = max(depth, (block.num_ilvl - floor) + 1)
    return depth


def _looks_like_prose(title: str) -> bool:
    """样式标题是否像被误套样式的整句正文（异常长，或较长且含句读标点）。

    用于把作者误用标题样式的整段话（如 TP试验程序里套了「章节标题」的实验说明句）
    标为 review 提请复核——解析仍忠实将其当章节，只是降信任度，不丢弃、不改层级。
    短名词短语标题（绝大多数真实标题）不触发。
    """
    n = len(title)
    if n >= _PROSE_LEN_HARD:
        return True
    return n >= _PROSE_LEN_SOFT and any(c in _PROSE_PUNCT for c in title)


def _attribution(
    block: Block, style_index: styles_mod.StyleIndex, stats: hd.DocStats
) -> tuple[str | None, str | None]:
    """计算标题节点的学习归因键 ``(source_style_name, source_numbering_pattern)``。

    样式标题 → 来源样式显示名（动态字典 ``heading_style_map`` 的 key）；启发式编号标题
    → 编号 ``pattern_key``（编号体例 profile 的 key）。二者互斥，无信号返回 None。
    """
    if block.style_level is not None:
        info = style_index.get(block.style_id)
        name = (info.name if info else None) or block.style_id
        return (name.strip() if name else None), None
    num = (
        hd.classify_numbering(block.text.strip(), stats.numbering_overrides)
        if block.text.strip()
        else None
    )
    return None, (num.pattern_key if num is not None else None)


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
            num = hd.classify_numbering(block.text.strip(), stats.numbering_overrides)
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
            ParseWarning(
                stage="completeness", message=f"图片可能遗漏：原始 {raw} / 解析 {ext}",
                severity="blocking",
            )
        )
    tbl_ok, traw, tser = completeness.table_count_match(body_blocks)
    if not tbl_ok:
        warnings.append(
            ParseWarning(
                stage="completeness", message=f"表格可能遗漏：原始 {traw} / 解析 {tser}",
                severity="blocking",
            )
        )
    p_ok, p_raw, p_kept = completeness.paragraph_count_match(nd)
    if not p_ok:
        warnings.append(
            ParseWarning(
                stage="completeness",
                message=f"段落可能遗漏：原始 {p_raw} / 解析 {p_kept}（保留 {p_kept/p_raw:.1%}）",
                severity="blocking",
            )
        )
    ph_ok, ph_raw, ph_ins = completeness.placeholder_count_match(body_blocks)
    if not ph_ok:
        warnings.append(
            ParseWarning(
                stage="completeness",
                message=f"公式/图示可能遗漏：原始 {ph_raw} / 占位 {ph_ins}",
                severity="blocking",
            )
        )
