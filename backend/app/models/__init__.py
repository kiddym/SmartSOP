"""ORM 模型包。

导入全部模型以填充 Base.metadata（供 Alembic / create_all 使用）并解析关系。
"""

from __future__ import annotations

from app.models.asset import ProcedureAsset, ProcedureAssetReference
from app.models.asset_category import AssetCategory
from app.models.asset_downtime import AssetDowntime
from app.models.maintenance_asset import Asset, AssetTeam, AssetUser
from app.models.location import Location, LocationTeam, LocationUser
from app.models.team import Team, TeamUser
from app.models.attachment import ProcedureAttachment
from app.models.audit import FolderAuditLog, ProcedureAuditLog
from app.models.base import Base
from app.models.company import Company
from app.models.field import ProcedureField
from app.models.folder import Folder, FolderSequence
from app.models.node import ProcedureNode
from app.models.procedure import Procedure
from app.models.sequence import Sequence
from app.models.settings import ProcedureSettings
from app.models.role import Role
from app.models.source_docx import ProcedureSourceDocx
from app.models.user import User
from app.models.work_order import WorkOrder, WorkOrderAssignee, WorkOrderTeam
from app.models.work_order_activity import WorkOrderActivity
from app.models.work_order_step_result import WorkOrderStepResult

__all__ = [
    "Asset",
    "AssetCategory",
    "AssetDowntime",
    "AssetTeam",
    "AssetUser",
    "Location",
    "LocationTeam",
    "LocationUser",
    "Team",
    "TeamUser",
    "Base",
    "Company",
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
    "Role",
    "Sequence",
    "User",
    "WorkOrder",
    "WorkOrderActivity",
    "WorkOrderAssignee",
    "WorkOrderStepResult",
    "WorkOrderTeam",
]
