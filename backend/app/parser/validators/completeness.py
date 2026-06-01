"""完整性对账（移植蓝本 §五 C001-C006 子集，Q348）。

C001 图片数 / C002 表格数 / C003 段落总数（100%）/ C004 章节数≥1 / C006 body_start 非 None。
C005（XML child order 同构）暂仍 deferred —— 需要原始 body 子序列与 blocks source_index
的结构化 diff，infra 成本高、real-world 价值低（normalize 顺序天然保真）。
"""

from __future__ import annotations

from collections.abc import Sequence

from app.parser.ir import Block, NormalizedDoc


def image_count_match(body_blocks: Sequence[Block]) -> tuple[bool, int, int]:
    """C001：正文范围原始 blip 数 vs 抽取 image 数。"""
    raw = sum(b.raw_image_count for b in body_blocks)
    extracted = sum(len(b.images) for b in body_blocks)
    return raw == extracted, raw, extracted


def table_count_match(body_blocks: Sequence[Block]) -> tuple[bool, int, int]:
    """C002：正文范围原始 w:tbl 数（含嵌套）vs 序列化 <table> 数。"""
    raw = sum(b.raw_table_count for b in body_blocks if b.kind == "table")
    serialized = sum(b.html.count("<table") for b in body_blocks if b.kind == "table")
    return raw == serialized, raw, serialized


def paragraph_count_match(nd: NormalizedDoc) -> tuple[bool, int, int]:
    """C003：body 内「应成块」的 <w:p> 数 vs normalize 输出的 paragraph block 数，100% 保留（kept == raw）才 pass。

    denominator 来自 normalize 阶段对 body.iter(w:p) 的过滤计数
    （`_counts_as_block_paragraph`）：顶层段落 + 文本框内段落计入，表格单元格直属
    段落被折叠进 table 块 HTML、不单独成块，故排除——否则含表文档（连参考模板自身）
    会因分母虚高而误报。触发场景是未来 _iter_body_children 或 _emit_txbx_descendants
    漏识某种 XML 形态导致段落静默丢失；当前 normalize 与该口径 1:1，预期总是 pass。
    """
    raw = nd.raw_paragraph_count
    kept = sum(1 for b in nd.blocks if b.kind == "paragraph")
    if raw == 0:
        return True, 0, kept
    ok = kept == raw
    return ok, raw, kept


def placeholder_count_match(body_blocks: Sequence[Block]) -> tuple[bool, int, int]:
    """C007：原始应占位数（独立扫描）vs 实际插入占位数。

    公式/SmartArt/chart 的兜底——独立扫描计 raw、序列化插入计 inserted，二者
    本应相等；不等说明插入路径漏插某形态，须报警以免静默丢失。
    """
    raw = sum(b.raw_placeholder_count for b in body_blocks)
    inserted = sum(b.placeholder_count for b in body_blocks)
    return raw == inserted, raw, inserted
