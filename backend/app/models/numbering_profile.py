"""动态标题字典 —— 编号体例模型（方案 M4b）。

按 ``pattern_key`` 覆盖内置编号判定（``classify_numbering`` 的 kind/level）。解析时读
``status='active'`` 拼 ``numbering_overrides`` 注入 ``parse_docx``。**仅作用本部署**，
绝不改全局编号规则代码（org 级隔离，方案 §3.2）。

例：本组织一贯把 ``第X条`` 当 L3 标题、把 ``N.N、`` 当 L2 → 各一条 active profile。
M4b 仅 ``source='manual'``；编号的隐式学习（source_numbering_pattern 归因 + 事件）待后续。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    UUIDMixin,
)


class NumberingProfile(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    """编号 pattern_key → (kind, level) 的体例覆盖（按租户隔离，(company_id, pattern_key) 唯一）。"""

    __tablename__ = "tb_numbering_profile"

    # classify_numbering 产出的 pattern_key（如「第X条」「N.N、」「一、」），租户内唯一。
    pattern_key: Mapped[str] = mapped_column(String(64))
    # 覆盖判定：'heading' | 'weak_heading' | 'list'（list=压制为非标题）。
    kind: Mapped[str] = mapped_column(String(20), default="heading", server_default="heading")
    # 1/2/3 = 标题层级；null = 沿用内置层级。
    level: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    source: Mapped[str] = mapped_column(String(20), default="manual", server_default="manual")
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active")
    # 预留给编号自学习（M4b 后续），M1/M4b-now 恒空。
    level_votes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    agreement: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    __table_args__ = (
        UniqueConstraint("company_id", "pattern_key", name="uq_numbering_profile_company_pattern"),
    )
