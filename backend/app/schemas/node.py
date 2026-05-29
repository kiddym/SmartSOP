"""统一节点 API schema(spec §4)。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NodeOut(BaseModel):
    """节点输出(GET 平铺 + 派生 parent_id/depth)。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    procedure_id: str
    sort_order: int
    heading_level: int | None
    kind: str
    body: str
    code: str
    skip_numbering: bool
    input_schema: dict[str, Any]
    attachment_marks: list[dict[str, Any]]
    mark_status: str
    revision: int
    parent_id: str | None
    depth: int


class NodePatchIn(BaseModel):
    """单节点 patch。仅传需要改的字段;heading_level 显式传 null 表示降为正文。"""

    model_config = ConfigDict(extra="forbid")

    heading_level: int | None = Field(default=None)
    kind: str | None = None
    body: str | None = None
    input_schema: dict[str, Any] | None = None
    attachment_marks: list[dict[str, Any]] | None = None
    skip_numbering: bool | None = None
    # 标记"本次 patch 是否要改 heading_level"(因 None 既是合法值又是默认值)。
    set_heading_level: bool = False


class NodeCreateIn(BaseModel):
    body: str = ""
    heading_level: int | None = None
    kind: str = "node"
    input_schema: dict[str, Any] = Field(default_factory=dict)
    attachment_marks: list[dict[str, Any]] = Field(default_factory=list)
    skip_numbering: bool = False
    sort_order: int | None = None


class NodeBatchItem(BaseModel):
    heading_level: int | None = None
    set_heading_level: bool = False
    kind: str | None = None
    input_schema: dict[str, Any] | None = None
    skip_numbering: bool | None = None


class NodeBatchIn(BaseModel):
    updates: dict[str, NodeBatchItem]


class NodeReorderIn(BaseModel):
    ordered_ids: list[str]
