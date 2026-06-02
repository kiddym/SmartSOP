from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class InviteUserRequest(BaseModel):
    email: EmailStr
    role_id: str | None = None


class InviteResult(BaseModel):
    id: str
    email: str
    status: str


class AcceptInviteRequest(BaseModel):
    token: str
    name: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=8, max_length=128)


class CurrencyCreate(BaseModel):
    code: str = Field(min_length=1, max_length=8)
    name: str = Field(min_length=1, max_length=64)
    symbol: str = Field(default="", max_length=8)


class CurrencyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    code: str
    name: str
    symbol: str


class CompanySettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    date_format: str
    timezone: str
    default_currency_code: str
    auto_assign: bool


class CompanySettingsUpdate(BaseModel):
    date_format: str | None = Field(default=None, max_length=32)
    timezone: str | None = Field(default=None, max_length=64)
    default_currency_code: str | None = Field(default=None, max_length=8)
    auto_assign: bool | None = None
