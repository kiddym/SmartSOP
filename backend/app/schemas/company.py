"""Company (tenant) settings schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.models.company import CompanyStatus


class CompanyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    slug: str
    status: CompanyStatus
    locale: str
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    employees_count: int | None = None
    logo_url: str | None = None


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    locale: str | None = Field(default=None, max_length=16)
    address: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=128)
    state: str | None = Field(default=None, max_length=128)
    zip_code: str | None = Field(default=None, max_length=32)
    phone: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=255)
    website: str | None = Field(default=None, max_length=255)
    employees_count: int | None = Field(default=None, ge=0)
    logo_url: str | None = Field(default=None, max_length=512)
