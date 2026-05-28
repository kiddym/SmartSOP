"""节点树派生(spec §2.2)。

父子关系不存,由 sort_order(输入已排序)+ heading_level 一次 O(n) 栈扫算出。
- heading(level!=None):弹栈直到栈顶 level < 本节点 level,栈顶为 parent,入栈。
- 正文/step(level=None):挂当前栈顶 heading,栈空则挂根。
跳级(L1→L3)被算法天然吸收(L3 挂 L1)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class NodeLike(Protocol):
    id: str
    heading_level: int | None


@dataclass
class TreeNode:
    id: str
    heading_level: int | None
    parent_id: str | None
    depth: int
    children: list["TreeNode"] = field(default_factory=list)


def build_tree(rows: list[NodeLike]) -> list[TreeNode]:
    """rows 必须已按 sort_order 升序。返回派生根节点列表。"""
    roots: list[TreeNode] = []
    stack: list[TreeNode] = []  # 当前祖先链(全是 heading)
    by_id: dict[str, TreeNode] = {}

    for row in rows:
        lvl = row.heading_level
        if lvl is None:
            parent = stack[-1] if stack else None
        else:
            while stack and (stack[-1].heading_level or 0) >= lvl:
                stack.pop()
            parent = stack[-1] if stack else None

        tn = TreeNode(
            id=row.id,
            heading_level=lvl,
            parent_id=parent.id if parent else None,
            depth=(parent.depth + 1) if parent else 0,
        )
        by_id[tn.id] = tn
        if parent is None:
            roots.append(tn)
        else:
            parent.children.append(tn)
        if lvl is not None:
            stack.append(tn)

    return roots
