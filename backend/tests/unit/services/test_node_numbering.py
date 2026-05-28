"""node_numbering.compute_codes 单测。"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.node_numbering import compute_codes


@dataclass
class Row:
    id: str
    heading_level: int | None
    kind: str = "node"
    skip_numbering: bool = False


def _rows(specs: list[tuple]) -> list[Row]:
    return [Row(*s) for s in specs]


def test_headings_hierarchical() -> None:
    rows = _rows([("a", 1), ("b", 2), ("c", 2), ("d", 1)])
    codes = compute_codes(rows)
    assert codes == {"a": "1", "b": "1.1", "c": "1.2", "d": "2"}


def test_content_never_numbered() -> None:
    rows = _rows([("a", 1), ("x", None, "node")])
    codes = compute_codes(rows)
    assert codes["a"] == "1"
    assert codes["x"] == ""


def test_step_numbered_under_heading() -> None:
    rows = _rows([("a", 1), ("s1", None, "step"), ("s2", None, "step")])
    codes = compute_codes(rows)
    assert codes["s1"] == "1.1"
    assert codes["s2"] == "1.2"


def test_skip_numbering_silences_subtree() -> None:
    rows = _rows([("a", 1, "node", True), ("b", 2), ("c", 1)])
    codes = compute_codes(rows)
    assert codes["a"] == ""
    assert codes["b"] == ""   # 父 skip → 子静默
    assert codes["c"] == "1"  # skip 不占位,c 仍是 1


def test_root_step_no_prefix() -> None:
    rows = _rows([("s", None, "step")])
    codes = compute_codes(rows)
    assert codes["s"] == "1"
