"""导入树 → ProcedureNode 扁平行（Plan B1 双写）。

把用户审查后的 `ImportNodeIn` 树（content_type + 嵌套深度）按文档顺序前序展开为
ProcedureNode 行的中间表示：chapter→heading_level=深度、content→heading_level=None，
全部 kind='node'。纯函数、不碰 DB；import_service 负责临时图 URL 提升与落库。
统一节点模型见 docs/superpowers/specs/2026-05-28-unified-node-model-design.md §5/§2。
"""

from __future__ import annotations

import html
from dataclasses import dataclass

from app.schemas.parse import ImportNodeIn


@dataclass
class FlatNode:
    """一行待落库的 ProcedureNode（body 为提升 URL 前的原始 HTML）。"""

    heading_level: int | None
    kind: str
    body: str
    mark_status: str
    skip_numbering: bool


def _chapter_body(title: str) -> str:
    """heading 的 body = 标题首段（spec §2.3）；空标题 → 空 body（占位章节）。"""
    title = title.strip()
    return f"<p>{html.escape(title)}</p>" if title else ""


def _clamp_mark_status(value: str) -> str:
    """统一模型 mark_status 只有 unmarked | review；脏值夹紧为 unmarked
    （沿用 import_service._create_node 的护栏语义）。"""
    return "review" if value == "review" else "unmarked"


def flatten_tree(chapters: list[ImportNodeIn]) -> list[FlatNode]:
    """前序展开为扁平行。chapters 应已过 import_service._normalize_for_exclusion。"""
    out: list[FlatNode] = []

    def walk(nodes: list[ImportNodeIn], level: int) -> None:
        for node in nodes:
            if node.content_type == "content":
                out.append(
                    FlatNode(
                        heading_level=None,
                        kind="node",
                        body=node.rich_content,
                        mark_status=_clamp_mark_status(node.mark_status),
                        skip_numbering=node.skip_numbering,
                    )
                )
                walk(node.children, level)  # content 一般无子；有也按同层处理
            else:
                out.append(
                    FlatNode(
                        heading_level=level,
                        kind="node",
                        body=_chapter_body(node.title),
                        mark_status=_clamp_mark_status(node.mark_status),
                        skip_numbering=node.skip_numbering,
                    )
                )
                walk(node.children, level + 1)

    walk(chapters, 1)
    return out
