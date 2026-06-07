"""ORM 模型包。

导入全部模型以填充 Base.metadata（供 Alembic / create_all 使用）并解析关系。
"""

from __future__ import annotations

from app.models.asset import ProcedureAsset, ProcedureAssetReference
from app.models.asset_category import AssetCategory
from app.models.asset_downtime import AssetDowntime
from app.models.attachment import Attachment
from app.models.audit import FolderAuditLog, ProcedureAuditLog
from app.models.base import Base
from app.models.batch import BatchImportItem, BatchImportJob
from app.models.billing_event import BillingEvent
from app.models.company import Company
from app.models.company_settings import CompanySettings
from app.models.cost_category import CostCategory
from app.models.currency import Currency
from app.models.custom_field_def import CustomFieldDef
from app.models.customer import Customer, CustomerAsset, CustomerLocation, CustomerPart
from app.models.deprecation import AssetDeprecation
from app.models.email_outbox import EmailOutbox
from app.models.field import ProcedureField
from app.models.floor_plan import FloorPlan
from app.models.folder import Folder, FolderSequence
from app.models.form_field_config import FormFieldConfig
from app.models.heading_learning_event import HeadingLearningEvent
from app.models.heading_rule import HeadingStyleRule
from app.models.location import Location, LocationTeam, LocationUser
from app.models.maintenance_asset import Asset, AssetTeam, AssetUser
from app.models.meter import Meter, MeterUser
from app.models.meter_category import MeterCategory
from app.models.meter_reading import MeterReading
from app.models.meter_trigger import MeterTrigger, MeterTriggerAssignee, MeterTriggerTeam
from app.models.multi_part import MultiPart, MultiPartItem
from app.models.node import ProcedureNode
from app.models.notification import Notification, NotificationArm
from app.models.notification_preference import NotificationPreference
from app.models.numbering_profile import NumberingProfile
from app.models.part import Part, PartAsset, PartAssignee, PartLocation, PartPM, PartTeam
from app.models.part_category import PartCategory
from app.models.part_consumption import PartConsumption
from app.models.password_reset_token import PasswordResetToken
from app.models.pm_activity import PMActivity
from app.models.preventive_maintenance import PMAssignee, PMTeam, PreventiveMaintenance
from app.models.procedure import Procedure
from app.models.purchase_order import (
    PurchaseOrder,
    PurchaseOrderActivity,
    PurchaseOrderLine,
)
from app.models.purchase_order_category import PurchaseOrderCategory
from app.models.push_token import PushToken
from app.models.request import Request
from app.models.request_activity import RequestActivity
from app.models.role import Role
from app.models.sequence import Sequence
from app.models.settings import ProcedureSettings
from app.models.source_docx import ProcedureSourceDocx
from app.models.super_account_relation import SuperAccountRelation
from app.models.team import Team, TeamUser
from app.models.time_category import TimeCategory
from app.models.user import User
from app.models.user_invitation import UserInvitation
from app.models.vendor import Vendor, VendorAsset, VendorLocation, VendorPart
from app.models.verification_token import VerificationToken
from app.models.work_order import WorkOrder, WorkOrderAssignee, WorkOrderTeam
from app.models.work_order_activity import WorkOrderActivity
from app.models.work_order_additional_cost import WorkOrderAdditionalCost
from app.models.work_order_category import WorkOrderCategory
from app.models.work_order_labor import WorkOrderLabor
from app.models.work_order_step_result import WorkOrderStepResult
from app.models.workflow import Workflow

__all__ = [
    "Asset",
    "AssetCategory",
    "AssetDeprecation",
    "AssetDowntime",
    "AssetTeam",
    "AssetUser",
    "Attachment",
    "Base",
    "BatchImportItem",
    "BatchImportJob",
    "BillingEvent",
    "Company",
    "CompanySettings",
    "CostCategory",
    "Currency",
    "CustomFieldDef",
    "Customer",
    "CustomerAsset",
    "CustomerLocation",
    "CustomerPart",
    "EmailOutbox",
    "FloorPlan",
    "Folder",
    "FolderAuditLog",
    "FolderSequence",
    "FormFieldConfig",
    "HeadingLearningEvent",
    "HeadingStyleRule",
    "Location",
    "LocationTeam",
    "LocationUser",
    "Meter",
    "MeterCategory",
    "MeterReading",
    "MeterTrigger",
    "MeterTriggerAssignee",
    "MeterTriggerTeam",
    "MeterUser",
    "MultiPart",
    "MultiPartItem",
    "Notification",
    "NotificationArm",
    "NotificationPreference",
    "NumberingProfile",
    "PMActivity",
    "PMAssignee",
    "PMTeam",
    "Part",
    "PartAsset",
    "PartAssignee",
    "PartCategory",
    "PartConsumption",
    "PartLocation",
    "PartPM",
    "PartTeam",
    "PasswordResetToken",
    "PreventiveMaintenance",
    "Procedure",
    "ProcedureAsset",
    "ProcedureAssetReference",
    "ProcedureAuditLog",
    "ProcedureField",
    "ProcedureNode",
    "ProcedureSettings",
    "ProcedureSourceDocx",
    "PurchaseOrder",
    "PurchaseOrderActivity",
    "PurchaseOrderCategory",
    "PurchaseOrderLine",
    "PushToken",
    "Request",
    "RequestActivity",
    "Role",
    "Sequence",
    "SuperAccountRelation",
    "Team",
    "TeamUser",
    "TimeCategory",
    "User",
    "UserInvitation",
    "Vendor",
    "VendorAsset",
    "VendorLocation",
    "VendorPart",
    "VerificationToken",
    "WorkOrder",
    "WorkOrderActivity",
    "WorkOrderAdditionalCost",
    "WorkOrderAssignee",
    "WorkOrderCategory",
    "WorkOrderLabor",
    "WorkOrderStepResult",
    "WorkOrderTeam",
    "Workflow",
]
