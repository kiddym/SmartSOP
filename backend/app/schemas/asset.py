"""资产 schema。"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.asset_status import AssetStatus


class AssetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    parent_id: str | None = None
    location_id: str | None = None
    category_id: str | None = None
    status: AssetStatus = AssetStatus.OPERATIONAL
    serial_number: str = ""
    model: str = ""
    manufacturer: str = ""
    power: str = ""
    warranty_expiration_date: date | None = None
    in_service_date: date | None = None
    acquisition_cost: Decimal | None = None
    barcode: str | None = None
    nfc_id: str | None = None
    primary_user_id: str | None = None
    assigned_user_ids: list[str] = []
    team_ids: list[str] = []


class AssetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    parent_id: str | None = None
    location_id: str | None = None
    category_id: str | None = None
    status: AssetStatus | None = None
    serial_number: str | None = None
    model: str | None = None
    manufacturer: str | None = None
    power: str | None = None
    warranty_expiration_date: date | None = None
    in_service_date: date | None = None
    acquisition_cost: Decimal | None = None
    barcode: str | None = None
    nfc_id: str | None = None
    primary_user_id: str | None = None
    assigned_user_ids: list[str] | None = None
    team_ids: list[str] | None = None


class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    custom_id: str
    name: str
    description: str
    parent_id: str | None = None
    location_id: str | None = None
    category_id: str | None = None
    status: AssetStatus
    serial_number: str
    model: str
    manufacturer: str
    power: str
    warranty_expiration_date: date | None = None
    in_service_date: date | None = None
    acquisition_cost: Decimal | None = None
    barcode: str | None = None
    nfc_id: str | None = None
    primary_user_id: str | None = None
    assigned_user_ids: list[str] = []
    team_ids: list[str] = []


class AssetMini(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    custom_id: str


class DowntimeCreate(BaseModel):
    started_at: datetime
    ended_at: datetime | None = None
    reason: str = ""
    downtime_type: str = "manual"


class DowntimeClose(BaseModel):
    ended_at: datetime


class DowntimeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    asset_id: str
    started_at: datetime
    ended_at: datetime | None = None
    reason: str
    downtime_type: str
    source_asset_id: str | None = None
