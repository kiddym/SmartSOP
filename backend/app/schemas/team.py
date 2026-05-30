"""团队 schema。"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = ""


class TeamUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None


class TeamMembersSet(BaseModel):
    user_ids: list[str] = []


class TeamRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: str
    member_ids: list[str] = []
