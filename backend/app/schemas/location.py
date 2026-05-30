"""位置 schema。"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LocationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    parent_id: str | None = None
    address: str = ""
    longitude: float | None = None
    latitude: float | None = None
    assigned_user_ids: list[str] = []
    team_ids: list[str] = []


class LocationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    parent_id: str | None = None
    address: str | None = None
    longitude: float | None = None
    latitude: float | None = None
    assigned_user_ids: list[str] | None = None
    team_ids: list[str] | None = None


class LocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    custom_id: str
    name: str
    description: str
    parent_id: str | None = None
    address: str
    longitude: float | None = None
    latitude: float | None = None
    assigned_user_ids: list[str] = []
    team_ids: list[str] = []


class LocationMini(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    custom_id: str
