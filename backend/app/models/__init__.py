"""ORM 模型包。

导入全部模型以填充 Base.metadata（供 Alembic / create_all 使用）并解析关系。
"""

from __future__ import annotations

from app.models.asset import ProcedureAsset, ProcedureAssetReference
from app.models.attachment import ProcedureAttachment
from app.models.audit import FolderAuditLog, ProcedureAuditLog
from app.models.base import Base
from app.models.field import ProcedureField
from app.models.folder import Folder, FolderSequence
from app.models.node import ProcedureNode
from app.models.procedure import Procedure
from app.models.settings import ProcedureSettings
from app.models.source_docx import ProcedureSourceDocx

__all__ = [
    "Base",
    "Folder",
    "FolderAuditLog",
    "FolderSequence",
    "Procedure",
    "ProcedureAsset",
    "ProcedureAssetReference",
    "ProcedureAttachment",
    "ProcedureAuditLog",
    "ProcedureField",
    "ProcedureNode",
    "ProcedureSettings",
    "ProcedureSourceDocx",
]
