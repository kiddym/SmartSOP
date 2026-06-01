"""层级标定 walk(等价于 frontend `computeLayerUpdates`,见 layerMark.ts:59)。

输入:文档序的 LayerRow 列表 + role map。输出:每行的 LayerUpdate(tagged dict)。
双端等价性由 backend/tests/fixtures/layer_walk_fixtures.json 锁住。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

LayerRole = Literal["chapter_1", "chapter_2", "chapter_3", "content", "keep"]
RowKind = Literal["chapter", "step", "content"]


@dataclass(frozen=True)
class LayerRow:
    id: str
    kind: RowKind
    level: int
    has_leaf_children: bool


def default_layer_role(row: LayerRow) -> LayerRole:
    if row.kind != "chapter":
        return "keep"
    lv = min(3, max(1, row.level))
    return f"chapter_{lv}"  # type: ignore[return-value]


def _effective_role(row: LayerRow, role_map: dict[str, LayerRole]) -> LayerRole:
    role = role_map.get(row.id, default_layer_role(row))
    if row.kind == "chapter":
        if role == "keep":
            return default_layer_role(row)
        return role
    if role == "content":
        return "keep"
    return role


def _role_level(role: LayerRole) -> int:
    return 3 if role == "chapter_3" else 2 if role == "chapter_2" else 1


def compute_layer_updates(rows: list[LayerRow], role_map: dict[str, LayerRole]) -> dict[str, dict]:
    """对应 frontend computeLayerUpdates。返回 dict[id, LayerUpdate],其中 LayerUpdate 为:
      {"kind": "reorder",       "parent_id": str|None, "sort_order": int, "level": int}
    | {"kind": "to-content",    "parent_id": str|None, "sort_order": int}
    | {"kind": "to-chapter",    "parent_id": str|None, "sort_order": int, "level": int}
    | {"kind": "leaf-reparent", "parent_id": str|None, "sort_order": int}
    """
    out: dict[str, dict] = {}
    l1: str | None = None
    l2: str | None = None
    l3: str | None = None
    sort_counter: dict[str | None, int] = {}

    def next_sort(p: str | None) -> int:
        n = sort_counter.get(p, 0)
        sort_counter[p] = n + 1
        return n

    def place_chapter(requested: int) -> tuple[str | None, int]:
        if requested >= 3 and l2 is not None:
            return l2, 3
        if requested >= 2 and l1 is not None:
            return l1, 2
        return None, 1

    def set_heading(row_id: str, level: int) -> None:
        nonlocal l1, l2, l3
        if level == 1:
            l1, l2, l3 = row_id, None, None
        elif level == 2:
            l2, l3 = row_id, None
        else:
            l3 = row_id

    for row in rows:
        role = _effective_role(row, role_map)
        if row.kind == "chapter":
            if role == "content":
                parent = l3 or l2 or l1
                out[row.id] = {
                    "kind": "to-content",
                    "parent_id": parent,
                    "sort_order": next_sort(parent),
                }
                continue
            requested = _role_level(role)
            parent, level = place_chapter(requested)
            set_heading(row.id, level)
            out[row.id] = {
                "kind": "reorder",
                "parent_id": parent,
                "sort_order": next_sort(parent),
                "level": level,
            }
            continue
        if role == "keep":
            parent = l3 or l2 or l1
            out[row.id] = {
                "kind": "leaf-reparent",
                "parent_id": parent,
                "sort_order": next_sort(parent),
            }
            continue
        requested = _role_level(role)
        parent, level = place_chapter(requested)
        set_heading(row.id, level)
        out[row.id] = {
            "kind": "to-chapter",
            "parent_id": parent,
            "sort_order": next_sort(parent),
            "level": level,
        }
    return out
