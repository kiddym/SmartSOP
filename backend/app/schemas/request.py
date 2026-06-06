"""请求 schema（Phase 2A）。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.asset_status import AssetStatus
from app.models.request_status import RequestStatus
from app.models.work_order_status import WorkOrderPriority


class RequestCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = ""
    priority: WorkOrderPriority = WorkOrderPriority.NONE
    due_date: date | None = None
    asset_id: str | None = None
    location_id: str | None = None
    custom_values: dict[str, Any] = {}


class RequestUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    priority: WorkOrderPriority | None = None
    due_date: date | None = None
    asset_id: str | None = None
    location_id: str | None = None
    custom_values: dict[str, Any] | None = None


class RequestApprove(BaseModel):
    note: str = ""
    primary_user_id: str | None = None
    assignee_ids: list[str] = []
    team_ids: list[str] = []
    procedure_id: str | None = None
    # 审批同时联动关联资产状态（可空）：仅当请求关联了资产时生效，走停机树联动路径。
    asset_status: AssetStatus | None = None


class RequestReason(BaseModel):
    reason: str = Field(min_length=1)


class RequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    custom_id: str
    title: str
    description: str
    priority: WorkOrderPriority
    due_date: date | None = None
    asset_id: str | None = None
    location_id: str | None = None
    status: RequestStatus
    work_order_id: str | None = None
    resolution_note: str
    resolved_by_user_id: str | None = None
    resolved_at: datetime | None = None
    custom_values: dict[str, Any] = {}


class CommentCreate(BaseModel):
    comment: str = Field(min_length=1)


class ActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    activity_type: str
    actor_user_id: str | None = None
    from_status: str | None = None
    to_status: str | None = None
    comment: str
    created_at: datetime
