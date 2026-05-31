"""动态标题字典 —— 样式规则模型（动态标题字典与自学习方案 M1，§3.1）。

覆盖内置 ``heading_synonyms.yaml``：按样式显示名映射层级。解析时读 ``status='active'``
规则拼成 ``style_overrides`` 注入 ``parse_docx``（优先级最高，见 styles.classify_with_source）。

- M1：``source='manual'``（管理员手动维护，即时 active）。
- M3：``source='learned'`` + 投票字段（level_votes / evidence_count / agreement）由聚合器写入；
  证据不足时 ``status='candidate'``（不应用、维持 review）。本表已预留这些列，避免二次迁移。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class HeadingStyleRule(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """样式名 → 层级 的动态规则（全局单租户，样式名唯一）。"""

    __tablename__ = "tb_heading_style_rule"

    # Word 样式显示名（如「章节标题」），动态字典 key。
    style_name: Mapped[str] = mapped_column(String(255), unique=True)
    # 1/2/3 = 标题层级；0/null = 显式判定「非标题/正文」。
    level: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    # 'manual'（手动钉死）| 'learned'（自学习）| 'disabled'（停用）。
    source: Mapped[str] = mapped_column(String(20), default="manual", server_default="manual")
    # 'active'（解析时应用）| 'candidate'（证据不足，暂不应用）。
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active")
    # 证据直方图 {"1":23,"2":1,"content":0}（M3 聚合用，M1 恒空）。
    level_votes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    agreement: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    # 乐观锁版本号（对齐 ProcedureSettings.revision 习惯）。
    revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
