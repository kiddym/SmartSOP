"""动态标题字典 —— 学习事件模型（方案 M3，§3.3）。

append-only 原始信号：用户在编辑器对**样式标题**的改级 / 标题↔正文互转 / review 确认，
按 (style_name, procedure_id) 累积。聚合器（heading_learning_service）按文档最新投票
推导 learned 规则。独立于审计表，保证聚合算法迭代后可重放、不丢训练数据。

M3 仅样式（style_name）；编号体例（numbering_pattern）的学习是 M4。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import DATETIME6, Base, utcnow

# 仿 audit.py：MySQL BIGINT 自增；SQLite 须 INTEGER 才能复用 rowid 自增。
_EVENT_PK = BigInteger().with_variant(Integer, "sqlite")


class HeadingLearningEvent(Base):
    """一条样式标题的用户校正信号（append-only）。"""

    __tablename__ = "tb_heading_learning_event"

    id: Mapped[int] = mapped_column(_EVENT_PK, primary_key=True, autoincrement=True)
    procedure_id: Mapped[str] = mapped_column(String(36), index=True)
    node_id: Mapped[str] = mapped_column(String(36))
    # 归因键：来源样式显示名（学习的 key）。
    style_name: Mapped[str] = mapped_column(String(255), index=True)
    # 'relevel' | 'demote_to_content' | 'promote_to_heading' | 'review_confirm'
    signal_type: Mapped[str] = mapped_column(String(30))
    from_level: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    # null = 正文（标题被降为正文）。
    to_level: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DATETIME6, default=utcnow)

    __table_args__ = (
        Index(
            "ix_tb_heading_learning_event_style_name_procedure_id",
            "style_name",
            "procedure_id",
        ),
    )
