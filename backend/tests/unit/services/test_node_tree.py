"""node_tree.build_tree 派生算法单测(spec §2.2)。"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.node_tree import build_tree


@dataclass
class Row:
    id: str
    heading_level: int | None


def _flat(rows: list[tuple[str, int | None]]) -> list[Row]:
    return [Row(id=i, heading_level=lvl) for i, lvl in rows]


def _by_id(tree_nodes):
    out = {}
    def walk(nodes):
        for n in nodes:
            out[n.id] = n
            walk(n.children)
    walk(tree_nodes)
    return out


def test_simple_nesting() -> None:
    rows = _flat([("a", 1), ("b", 2), ("x", None), ("y", None)])
    roots = build_tree(rows)
    nodes = _by_id(roots)
    assert [r.id for r in roots] == ["a"]
    assert nodes["a"].parent_id is None and nodes["a"].depth == 0
    assert nodes["b"].parent_id == "a" and nodes["b"].depth == 1
    assert nodes["x"].parent_id == "b" and nodes["y"].parent_id == "b"


def test_content_before_any_heading_is_root() -> None:
    rows = _flat([("x", None), ("a", 1)])
    nodes = _by_id(build_tree(rows))
    assert nodes["x"].parent_id is None
    assert nodes["a"].parent_id is None


def test_skip_level_l1_to_l3() -> None:
    rows = _flat([("a", 1), ("c", 3)])
    nodes = _by_id(build_tree(rows))
    assert nodes["c"].parent_id == "a" and nodes["c"].depth == 1


def test_demote_reparents_following_content() -> None:
    # a(L1) > [b(L2 demoted->null), x, y], c(L2)
    rows = _flat([("a", 1), ("b", None), ("x", None), ("y", None), ("c", 2)])
    nodes = _by_id(build_tree(rows))
    assert nodes["b"].parent_id == "a"
    assert nodes["x"].parent_id == "a"
    assert nodes["y"].parent_id == "a"
    assert nodes["c"].parent_id == "a"


def test_promote_captures_following_content() -> None:
    # a(L2) > x(L3 promoted), y, z  then b(L2)
    rows = _flat([("a", 2), ("x", 3), ("y", None), ("z", None), ("b", 2)])
    nodes = _by_id(build_tree(rows))
    assert nodes["x"].parent_id == "a"
    assert nodes["y"].parent_id == "x"
    assert nodes["z"].parent_id == "x"
    assert nodes["b"].parent_id is None  # b pops a(L2), no L1 above -> root


def test_sibling_l2s_share_l1_parent() -> None:
    rows = _flat([("a", 1), ("b", 2), ("c", 2)])
    nodes = _by_id(build_tree(rows))
    assert nodes["b"].parent_id == "a"
    assert nodes["c"].parent_id == "a"
