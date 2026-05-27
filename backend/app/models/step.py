"""程序步骤模型（data-model §3.5）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import LONGTEXT, Base, SoftDeleteMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.chapter import ProcedureChapter
    from app.models.procedure import Procedure


class ProcedureStep(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """步骤节点（执行表单定义；执行运行时态本期不实现，Q264）。"""

    __tablename__ = "tb_procedure_step"

    procedure_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tb_procedure.id", ondelete="RESTRICT")
    )
    chapter_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_procedure_chapter.id", ondelete="RESTRICT")
    )
    title: Mapped[str] = mapped_column(String(500), default="", server_default="")
    code: Mapped[str] = mapped_column(String(50), default="", server_default="")
    content: Mapped[str] = mapped_column(LONGTEXT, default="", server_default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    skip_numbering: Mapped[bool] = mapped_column(default=False, server_default="0")
    # 执行表单 15 型（大写枚举，Q261/Q262；NOTE/CAUTION/WARNING 警示已并入 type）
    input_schema: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # 步骤级附件标记（仅标记，不嵌文件，Q203）
    attachment_marks: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    # 节点 kind：
    #   step    = title?（可选） + content（富文本） + 结构化字段（input_schema 表单 / attachment_marks 附件）
    #   content = title?（可选） + content（富文本）；不带结构化字段
    # 两者结构相同（同表 tb_procedure_step），区别仅"是否带表单/附件结构"；
    # 升为章节走 conversion_service.convert_to_chapter（不分 kind）。
    kind: Mapped[str] = mapped_column(String(20), default="step", server_default="step")
    procedure: Mapped[Procedure] = relationship(back_populates="steps")
    chapter: Mapped[ProcedureChapter | None] = relationship(back_populates="steps")

    __table_args__ = (
        Index("ix_tb_procedure_step_procedure_id_sort_order", "procedure_id", "sort_order"),
        Index("ix_tb_procedure_step_chapter_id", "chapter_id"),
        Index("ix_tb_procedure_step_kind", "kind"),
    )
