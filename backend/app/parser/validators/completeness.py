"""完整性对账（移植蓝本 §五 C001-C006 子集，Q348）。

C001 图片数 / C002 表格数 / C003 段落总数（≥95%）/ C004 章节数≥1 / C006 body_start 非 None。
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
    """C003：body 内原始 <w:p> 数 vs normalize 输出的 paragraph block 数，保留率 ≥ 95% pass。

    本检查作用于全局 blocks（不限 body 范围），denominator 来自 normalize 阶段
    一次性 `body.iter(qn("w:p"))` 全量计数，触发场景是未来 _iter_body_children
    或 _emit_txbx_descendants 漏识某种 XML 形态导致段落静默丢失。当前 normalize
    与 raw 严格 1:1，预期总是 pass；本检查是 forward-looking guard。
    """
    raw = nd.raw_paragraph_count
    kept = sum(1 for b in nd.blocks if b.kind == "paragraph")
    if raw == 0:
        return True, 0, kept
    ok = kept / raw >= 0.95
    return ok, raw, kept
