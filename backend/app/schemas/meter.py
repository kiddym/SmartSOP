"""Meter schema（Phase 2C）。is_armed/last_* 不可写（由 service 维护）。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.meter_comparator import MeterComparator
from app.models.work_order_status import WorkOrderPriority


class MeterCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    unit: str = Field(default="", max_length=50)
    update_frequency_days: int | None = Field(default=None, ge=1)
    asset_id: str | None = None
    location_id: str | None = None
    meter_category_id: str | None = None
    image_url: str | None = Field(default=None, max_length=512)
    user_ids: list[str] | None = None


class MeterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    unit: str | None = Field(default=None, max_length=50)
    update_frequency_days: int | None = Field(default=None, ge=1)
    asset_id: str | None = None
    location_id: str | None = None
    meter_category_id: str | None = None
    image_url: str | None = Field(default=None, max_length=512)
    user_ids: list[str] | None = None


class MeterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    custom_id: str
    name: str
    unit: str
    update_frequency_days: int | None = None
    asset_id: str | None = None
    location_id: str | None = None
    meter_category_id: str | None = None
    image_url: str | None = None
    user_ids: list[str] = []


class MeterReadingCreate(BaseModel):
    value: Decimal
    reading_at: datetime | None = None


class MeterReadingUpdate(BaseModel):
    value: Decimal | None = None
    reading_at: datetime | None = None


class MeterReadingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    meter_id: str
    value: Decimal
    reading_at: datetime
    recorded_by_user_id: str | None = None


class TriggerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    comparator: MeterComparator
    threshold: Decimal
    priority: WorkOrderPriority = WorkOrderPriority.NONE
    title: str = Field(min_length=1, max_length=300)
    description: str = ""
    primary_user_id: str | None = None
    procedure_id: str | None = None
    assignee_ids: list[str] = []
    team_ids: list[str] = []


class TriggerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    comparator: MeterComparator | None = None
    threshold: Decimal | None = None
    priority: WorkOrderPriority | None = None
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    primary_user_id: str | None = None
    procedure_id: str | None = None
    assignee_ids: list[str] | None = None
    team_ids: list[str] | None = None


class TriggerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    meter_id: str
    name: str
    comparator: MeterComparator
    threshold: Decimal
    is_armed: bool
    is_enabled: bool
    priority: WorkOrderPriority
    title: str
    description: str
    primary_user_id: str | None = None
    procedure_id: str | None = None
    assignee_ids: list[str] = []
    team_ids: list[str] = []
    last_triggered_at: datetime | None = None
    last_work_order_id: str | None = None


class ReadingResult(BaseModel):
    reading: MeterReadingRead
    generated_work_order_ids: list[str] = []
