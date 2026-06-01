"""Completeness validators 单测：C001 图片对账、C002 表格对账。

覆盖正向（分母分子相等→pass）与反向（分母 > 分子→fail，触发 warning 路径）。
"""

from __future__ import annotations

from app.parser.ir import Block, ImageRef
from app.parser.validators import completeness


def _img(rid: str = "rId1") -> ImageRef:
    return ImageRef(rid=rid, part_name="word/media/x.png", data=b"x", ext=".png")


def test_c001_passes_when_raw_equals_extracted() -> None:
    blocks = [
        Block(kind="paragraph", source_index=0, raw_image_count=2, images=[_img("a"), _img("b")]),
        Block(kind="paragraph", source_index=1, raw_image_count=0, images=[]),
    ]
    ok, raw, ext = completeness.image_count_match(blocks)
    assert ok is True
    assert raw == 2 and ext == 2


def test_c001_fails_when_raw_exceeds_extracted() -> None:
    """模拟一张图被 _emit_images 跳过（损坏 / rid 未注册）—— C001 应能识别。"""
    blocks = [
        Block(kind="paragraph", source_index=0, raw_image_count=2, images=[_img("only_one")]),
    ]
    ok, raw, ext = completeness.image_count_match(blocks)
    assert ok is False
    assert raw == 2 and ext == 1


def test_c002_passes_when_table_raw_equals_serialized() -> None:
    blocks = [
        Block(
            kind="table",
            source_index=0,
            html="<table><tr><td>x</td></tr></table>",
            raw_table_count=1,
        ),
    ]
    ok, raw, ser = completeness.table_count_match(blocks)
    assert ok is True
    assert raw == 1 and ser == 1


def test_c002_fails_when_nested_table_not_serialized() -> None:
    """嵌套表：原始 2 个 w:tbl（外+内）但 HTML 只渲染了 1 个 → C002 fail。"""
    blocks = [
        Block(
            kind="table",
            source_index=0,
            html="<table><tr><td>only_outer</td></tr></table>",  # 内嵌表丢失
            raw_table_count=2,
        ),
    ]
    ok, raw, ser = completeness.table_count_match(blocks)
    assert ok is False
    assert raw == 2 and ser == 1


def test_c003_passes_when_kept_above_95_percent() -> None:
    """C003：100% 保留 → pass。"""
    from app.parser.ir import NormalizedDoc

    blocks = [Block(kind="paragraph", source_index=i) for i in range(20)]
    nd = NormalizedDoc(blocks=blocks, raw_paragraph_count=20)
    ok, raw, kept = completeness.paragraph_count_match(nd)
    assert ok is True
    assert raw == 20 and kept == 20


def test_c003_passes_only_when_kept_equals_raw() -> None:
    """C003：100% 保留（kept == raw）→ pass。"""
    from app.parser.ir import NormalizedDoc

    blocks = [Block(kind="paragraph", source_index=i) for i in range(20)]
    nd = NormalizedDoc(blocks=blocks, raw_paragraph_count=20)
    ok, raw, kept = completeness.paragraph_count_match(nd)
    assert ok is True
    assert raw == 20 and kept == 20


def test_c003_fails_at_95_percent() -> None:
    """C003：19/20 = 95% 现在应当 fail（阈值已提至 100%）。"""
    from app.parser.ir import NormalizedDoc

    blocks = [Block(kind="paragraph", source_index=i) for i in range(19)]
    nd = NormalizedDoc(blocks=blocks, raw_paragraph_count=20)
    ok, raw, kept = completeness.paragraph_count_match(nd)
    assert ok is False  # 19/20 < 100%
    assert raw == 20 and kept == 19


def test_c003_fails_when_one_paragraph_dropped() -> None:
    """C003：丢 1 段（模拟 normalize 漏抽）→ fail。"""
    from app.parser.ir import NormalizedDoc

    blocks = [Block(kind="paragraph", source_index=i) for i in range(18)]
    nd = NormalizedDoc(blocks=blocks, raw_paragraph_count=20)
    ok, raw, kept = completeness.paragraph_count_match(nd)
    assert ok is False
    assert raw == 20 and kept == 18


def test_c003_passes_when_raw_is_zero() -> None:
    """C003：空文档（raw=0）应当 pass，避免除零异常。"""
    from app.parser.ir import NormalizedDoc

    nd = NormalizedDoc(blocks=[], raw_paragraph_count=0)
    ok, raw, kept = completeness.paragraph_count_match(nd)
    assert ok is True
    assert raw == 0 and kept == 0


def test_c007_passes_when_raw_equals_inserted() -> None:
    blocks = [
        Block(kind="paragraph", source_index=0, raw_placeholder_count=2, placeholder_count=2),
        Block(kind="paragraph", source_index=1, raw_placeholder_count=0, placeholder_count=0),
    ]
    ok, raw, inserted = completeness.placeholder_count_match(blocks)
    assert ok is True and raw == 2 and inserted == 2


def test_c007_fails_when_placeholder_missing() -> None:
    blocks = [
        Block(kind="paragraph", source_index=0, raw_placeholder_count=3, placeholder_count=2),
    ]
    ok, raw, inserted = completeness.placeholder_count_match(blocks)
    assert ok is False and raw == 3 and inserted == 2
