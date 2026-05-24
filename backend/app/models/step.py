"""程序步骤模型（data-model §3.5）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text
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
    # 执行表单 12 型（大写枚举，Q261/Q262）
    input_schema: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # 三警示富文本（ANSI Z535 三色，Q263 方案 A）
    note: Mapped[str] = mapped_column(LONGTEXT, default="", server_default="")
    caution: Mapped[str] = mapped_column(LONGTEXT, default="", server_default="")
    warning: Mapped[str] = mapped_column(LONGTEXT, default="", server_default="")
    # 三警示执行表单类型（与 input_schema 同构，默认 COMMON 即富文本）
    note_schema: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    caution_schema: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    warning_schema: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    expected_output: Mapped[str] = mapped_column(Text, default="", server_default="")
    # 步骤级附件标记（仅标记，不嵌文件，Q203）
    attachment_marks: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    require_confirmation: Mapped[bool] = mapped_column(default=False, server_default="0")

    procedure: Mapped[Procedure] = relationship(back_populates="steps")
    chapter: Mapped[ProcedureChapter | None] = relationship(back_populates="steps")

    __table_args__ = (
        Index("ix_tb_procedure_step_procedure_id_sort_order", "procedure_id", "sort_order"),
        Index("ix_tb_procedure_step_chapter_id", "chapter_id"),
    )
