"""统一节点模型(tb_procedure_node)。

单表表达章节/正文/步骤三态:
- heading_level: int|null —— null=正文;1/2/3…=章节层级
- kind: 'node'|'step'    —— 'node'=无表单(章节或正文);'step'=带 input_schema 表单
父子关系不存,由 sort_order+heading_level 派生(见 services/node_tree.py)。
统一节点模型：单表 ProcedureNode 取代旧 chapter/step 三分（旧表已于 B4 删除）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import LONGTEXT, Base, SoftDeleteMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.procedure import Procedure


class ProcedureNode(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """统一节点(章节 / 正文 / 步骤同表)。"""

    __tablename__ = "tb_procedure_node"

    procedure_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_procedure.id", ondelete="RESTRICT")
    )
    # 全局有序(per procedure 的扁平位置),不再 per-parent。
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # null=正文;>=1=章节层级(跳级允许,见 spec §3.4)。
    heading_level: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    # 'node'=无表单(章节或正文);'step'=带表单。
    kind: Mapped[str] = mapped_column(String(20), default="node", server_default="node")
    # rich HTML。heading 的"标题"= body 第一个块级元素文本(派生,见 spec §2.3)。
    body: Mapped[str] = mapped_column(LONGTEXT, default="", server_default="")
    code: Mapped[str] = mapped_column(String(50), default="", server_default="")
    skip_numbering: Mapped[bool] = mapped_column(default=False, server_default="0")
    # 仅 kind='step' 非空。
    input_schema: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    attachment_marks: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    # 解析存疑标记(parser 产出):'unmarked' | 'review'。
    mark_status: Mapped[str] = mapped_column(
        String(20), default="unmarked", server_default="unmarked"
    )
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")

    procedure: Mapped[Procedure] = relationship()

    __table_args__ = (
        Index("ix_tb_procedure_node_procedure_id_sort_order", "procedure_id", "sort_order"),
        Index("ix_tb_procedure_node_mark_status", "mark_status"),
    )
