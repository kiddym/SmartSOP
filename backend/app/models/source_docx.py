"""原始 Word 源文件模型（P1：导入可追溯）。

一个 procedure_group 至多存一份原始 .docx（导入时落库），供编辑器预览栏渲染、
正式后长期追溯。不去重、不软删（随版本组删除即物理清理）。
"""

from __future__ import annotations

from sqlalchemy import BigInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class ProcedureSourceDocx(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """导入程序的原始 .docx（按 procedure_group 归属，本公司内唯一）。"""

    __tablename__ = "tb_procedure_source_docx"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "procedure_group_id",
            name="uq_tb_procedure_source_docx_company_procedure_group",
        ),
    )

    procedure_group_id: Mapped[str] = mapped_column(String(64), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(500))
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
