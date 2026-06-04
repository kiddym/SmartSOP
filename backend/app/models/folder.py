"""文件夹与编号序列模型（data-model §3.1 / §3.2）。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    DATETIME6,
    Base,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    UUIDMixin,
)


class Folder(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    """文件夹（树形，max_depth=5）。容器 xor 叶子（Q247）。"""

    __tablename__ = "tb_folder"

    name: Mapped[str] = mapped_column(String(100))
    # 叶子必填非空 + 全局唯一（Q248）；中间容器恒空（Q247）；prefix 永久占用（Q249）
    prefix: Mapped[str] = mapped_column(String(20), default="", server_default="")
    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tb_folder.id", ondelete="RESTRICT"), index=True
    )
    # 系统文件夹（「废止」）禁止删除 / 改名
    system: Mapped[bool] = mapped_column(default=False, server_default="0")
    full_path: Mapped[str] = mapped_column(Text, default="", server_default="")

    parent: Mapped[Folder | None] = relationship(remote_side="Folder.id", back_populates="children")
    children: Mapped[list[Folder]] = relationship(back_populates="parent")
    sequence: Mapped[FolderSequence | None] = relationship(back_populates="folder", uselist=False)


class FolderSequence(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    """叶子文件夹的编号序列生成器（1:1）。仅叶子有此记录（Q247）。"""

    __tablename__ = "tb_folder_sequence"

    folder_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tb_folder.id", ondelete="RESTRICT"),
        unique=True,
        index=True,
    )
    current_value: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # 补零位数默认 5（Q250，生成 00001）
    sequence_digits: Mapped[int] = mapped_column(Integer, default=5, server_default="5")
    # 固定 never、不暴露（Q251）：序列只增不重置
    reset_period: Mapped[str] = mapped_column(String(20), default="never", server_default="never")
    last_reset_at: Mapped[datetime | None] = mapped_column(DATETIME6, default=None)

    folder: Mapped[Folder] = relationship(back_populates="sequence")
