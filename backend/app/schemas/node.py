"""章节 / 步骤（节点）schema（api-specification §5.4 / data-model §3.4-3.5 / §19 / §40）。

章节树由 tb_procedure_chapter 自引用（纯标题/分组容器）+
tb_procedure_step（步骤，kind=step 普通步骤 / kind=content 内容块）构成。
编号 code 全自动（§47），不接受手填。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MarkStatus = Literal["unmarked", "step", "content"]

# 执行表单 15 型（大写枚举，Q261/§40.1）
FORM_TYPES: frozenset[str] = frozenset(
    {
        "COMMON",
        "NOTE",
        "CAUTION",
        "WARNING",
        "CHECK",
        "YESNO",
        "NUMBER",
        "METER",
        "CHECKBOX",
        "RADIO",
        "UPLOAD",
        "SIGNATURE",
        "DATE",
        "PHOTO",
        "NONE",
    }
)


# --------------------------------------------------------------------------- #
# 章节 CRUD
# --------------------------------------------------------------------------- #
class ChapterCreate(BaseModel):
    """新增章节（分组容器）。code 由后端整树重算。"""

    procedure_id: str
    parent_id: str | None = None
    title: str = Field(default="", max_length=500)
    skip_numbering: bool = False
    sort_order: int | None = None  # None = 追加到同级末尾


class ChapterUpdate(BaseModel):
    """更新章节（content_type 不可改，改类型走 convert-*）。"""

    title: str = Field(default="", max_length=500)
    skip_numbering: bool = False


class ChapterMoveIn(BaseModel):
    """跨 parent 移动（body: target_parent_id + target_index）。"""

    target_parent_id: str | None = None
    target_index: int = Field(default=0, ge=0)


class MarkStatusIn(BaseModel):
    """设置单节点 mark_status（标记模式，Q2/Q3）。"""

    mark_status: MarkStatus


# --------------------------------------------------------------------------- #
# 步骤 CRUD
# --------------------------------------------------------------------------- #
class StepCreate(BaseModel):
    """新增步骤（受 Q25 互斥校验）。"""

    procedure_id: str
    chapter_id: str | None = None
    kind: Literal["step", "content"] = "step"
    title: str = Field(default="", max_length=500)
    content: str = Field(default="")
    input_schema: dict[str, Any] = Field(default_factory=lambda: {"type": "COMMON"})
    attachment_marks: list[dict[str, Any]] = Field(default_factory=list)
    skip_numbering: bool = False
    sort_order: int | None = None


class StepUpdate(BaseModel):
    """更新步骤。"""

    kind: Literal["step", "content"] = "step"
    title: str = Field(default="", max_length=500)
    content: str = Field(default="")
    input_schema: dict[str, Any] = Field(default_factory=lambda: {"type": "COMMON"})
    attachment_marks: list[dict[str, Any]] = Field(default_factory=list)
    skip_numbering: bool = False


class StepMoveIn(BaseModel):
    """跨 chapter 移动（body: target_chapter_id + target_index）。"""

    target_chapter_id: str | None = None
    target_index: int = Field(default=0, ge=0)


# --------------------------------------------------------------------------- #
# 批量保存（编辑器 PUT /procedures/{id} 的脏节点 upsert，§17.2 / Q154-Q155）
# --------------------------------------------------------------------------- #
class ChapterUpsert(BaseModel):
    """脏章节。id 为新建临时 id 或既有真实 id；parent_id 同理（后端 id 映射）。"""

    id: str
    parent_id: str | None = None
    title: str = Field(default="", max_length=500)
    skip_numbering: bool = False
    sort_order: int = 0


class StepUpsert(BaseModel):
    """脏步骤。id / chapter_id 为临时或真实 id（后端 id 映射）。"""

    id: str
    chapter_id: str | None = None
    kind: Literal["step", "content"] = "step"
    title: str = Field(default="", max_length=500)
    content: str = Field(default="")
    input_schema: dict[str, Any] = Field(default_factory=lambda: {"type": "COMMON"})
    attachment_marks: list[dict[str, Any]] = Field(default_factory=list)
    skip_numbering: bool = False
    sort_order: int = 0


# --------------------------------------------------------------------------- #
# 输出
# --------------------------------------------------------------------------- #
class StepOut(BaseModel):
    """步骤输出（GET /procedures/{id}.steps 平铺；前端按 chapter_id 自挂载）。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    procedure_id: str
    chapter_id: str | None
    kind: Literal["step", "content"] = "step"
    title: str
    code: str
    content: str
    sort_order: int
    skip_numbering: bool
    input_schema: dict[str, Any]
    attachment_marks: list[dict[str, Any]]


class ChapterOut(BaseModel):
    """单章节详情（GET /chapters/{id}），不含 children。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    procedure_id: str
    parent_id: str | None
    title: str
    code: str
    level: int
    sort_order: int
    skip_numbering: bool
    mark_status: str


class ChapterTreeNode(BaseModel):
    """嵌套章节树节点（GET /procedures/{id}.chapters）。"""

    id: str
    title: str
    code: str
    level: int
    sort_order: int
    skip_numbering: bool
    mark_status: str
    children: list[ChapterTreeNode] = Field(default_factory=list)


ChapterTreeNode.model_rebuild()


# --------------------------------------------------------------------------- #
# 转换 / 标记结果（Phase 5）
# --------------------------------------------------------------------------- #
class ConversionResult(BaseModel):
    """转换结果：新建 / 删除节点 ID。"""

    created: list[str] = Field(default_factory=list)
    deleted: list[str] = Field(default_factory=list)


class ApplyMarksResult(BaseModel):
    """应用标记结果（原子事务，Q9）：新建步骤 ID + 删除节点 ID。"""

    created: list[str] = Field(default_factory=list)
    deleted: list[str] = Field(default_factory=list)


class SplitTitleContentIn(BaseModel):
    """章节标题拆分请求：cursor_offset 必须在 (0, len(title)) 开区间内。"""

    cursor_offset: int = Field(..., gt=0)
