"""node_import.flatten_tree 单测（Plan B1 导入双写）。"""

from __future__ import annotations

from app.schemas.parse import ImportNodeIn
from app.services.node_import import FlatNode, flatten_tree


def _ch(title: str, children: list[ImportNodeIn] | None = None,
        mark_status: str = "unmarked", skip_numbering: bool = False) -> ImportNodeIn:
    return ImportNodeIn(
        title=title, content_type="chapter", children=children or [],
        mark_status=mark_status, skip_numbering=skip_numbering,
    )


def _co(rich: str, mark_status: str = "unmarked", skip_numbering: bool = False) -> ImportNodeIn:
    return ImportNodeIn(
        content_type="content", rich_content=rich,
        mark_status=mark_status, skip_numbering=skip_numbering,
    )


def test_flatten_preorder_and_levels() -> None:
    tree = [
        _ch("目的", [_co("<p>x</p>")]),
        _ch("职责", [_ch("质量部", [_co("<p>y</p>")])]),
    ]
    flat = flatten_tree(tree)
    assert [(f.heading_level, f.kind) for f in flat] == [
        (1, "node"), (None, "node"), (1, "node"), (2, "node"), (None, "node"),
    ]


def test_chapter_body_wraps_title() -> None:
    flat = flatten_tree([_ch("概述")])
    assert flat[0].body == "<p>概述</p>"


def test_empty_title_chapter_body_empty() -> None:
    flat = flatten_tree([_ch("   ")])
    assert flat[0].body == ""


def test_content_body_passthrough_and_level_none() -> None:
    flat = flatten_tree([_co("<p>原文<b>富</b></p>")])
    assert flat[0].body == "<p>原文<b>富</b></p>"
    assert flat[0].heading_level is None


def test_title_html_escaped() -> None:
    flat = flatten_tree([_ch("A & <B>")])
    assert flat[0].body == "<p>A &amp; &lt;B&gt;</p>"


def test_mark_status_and_skip_carried() -> None:
    flat = flatten_tree([_ch("待确认章", mark_status="review", skip_numbering=True)])
    assert flat[0].mark_status == "review"
    assert flat[0].skip_numbering is True


def test_dirty_mark_status_clamped_to_unmarked() -> None:
    flat = flatten_tree([_ch("章", mark_status="garbage")])
    assert flat[0].mark_status == "unmarked"
