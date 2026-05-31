"""PM schema（Phase 2B）。next_due_date 不可写（由 service 维护）。"""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.pm_frequency import PMFrequencyUnit
from app.models.work_order_status import WorkOrderPriority


class PMCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = ""
    priority: WorkOrderPriority = WorkOrderPriority.NONE
    asset_id: str | None = None
    location_id: str | None = None
    primary_user_id: str | None = None
    procedure_id: str | None = None
    assignee_ids: list[str] = []
    team_ids: list[str] = []
    start_date: date
    frequency_unit: PMFrequencyUnit
    frequency_value: int = Field(ge=1)


class PMUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    priority: WorkOrderPriority | None = None
    asset_id: str | None = None
    location_id: str | None = None
    primary_user_id: str | None = None
    procedure_id: str | None = None
    assignee_ids: list[str] | None = None
    team_ids: list[str] | None = None
    start_date: date | None = None
    frequency_unit: PMFrequencyUnit | None = None
    frequency_value: int | None = Field(default=None, ge=1)


class PMRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    custom_id: str
    title: str
    description: str
    priority: WorkOrderPriority
    asset_id: str | None = None
    location_id: str | None = None
    primary_user_id: str | None = None
    procedure_id: str | None = None
    assignee_ids: list[str] = []
    team_ids: list[str] = []
    start_date: date
    frequency_unit: PMFrequencyUnit
    frequency_value: int
    next_due_date: date
    is_enabled: bool
    last_generated_at: datetime | None = None
    last_work_order_id: str | None = None


class PMActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    activity_type: str
    actor_user_id: str | None = None
    comment: str
    created_at: datetime


class CommentCreate(BaseModel):
    comment: str = Field(min_length=1)
