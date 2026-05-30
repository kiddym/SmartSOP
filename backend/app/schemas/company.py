"""Company (tenant) settings schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field, ConfigDict

from app.models.company import CompanyStatus


class CompanyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    slug: str
    status: CompanyStatus
    locale: str


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    locale: str | None = Field(default=None, max_length=16)
