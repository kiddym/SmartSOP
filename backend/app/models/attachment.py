"""通用附件模型：多态挂任意业务实体（entity_type + entity_id，无硬 FK）。"""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    UUIDMixin,
)


class Attachment(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, TenantMixin):
    """通用附件（多态软关联宿主实体；procedure 经 entity_type='procedure' 平移）。"""

    __tablename__ = "tb_attachment"

    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[str] = mapped_column(String(36))
    file_name: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    description: Mapped[str] = mapped_column(Text, default="", server_default=text("('')"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # 文件大类：上传时按 MIME/扩展名推断（图片→'IMAGE'，否则 'OTHER'）。供全局文件库筛选。
    file_type: Mapped[str] = mapped_column(
        String(16), default="OTHER", server_default=text("('OTHER')")
    )
    # 隐藏标记：软隐藏（仍存在/可下载），用于全局文件库默认隐藏过滤。
    hidden: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("0"))

    __table_args__ = (
        Index("ix_tb_attachment_entity", "entity_type", "entity_id"),
        Index("ix_tb_attachment_storage_path", "storage_path"),
    )
