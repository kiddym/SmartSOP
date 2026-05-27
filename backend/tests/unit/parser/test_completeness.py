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
