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
    language: str
    business_type: str | None = None
    wo_update_for_requesters: bool
    disable_closed_wo_notification: bool
    ask_feedback_on_wo_closed: bool
    labor_cost_in_total_cost: bool
    simplified_work_order: bool
    days_before_pm_notification: int
    auto_assign_requests: bool


class CompanySettingsUpdate(BaseModel):
    date_format: str | None = Field(default=None, max_length=32)
    timezone: str | None = Field(default=None, max_length=64)
    default_currency_code: str | None = Field(default=None, max_length=8)
    auto_assign: bool | None = None
    language: str | None = Field(default=None, max_length=16)
    business_type: str | None = Field(default=None, max_length=64)
    wo_update_for_requesters: bool | None = None
    disable_closed_wo_notification: bool | None = None
    ask_feedback_on_wo_closed: bool | None = None
    labor_cost_in_total_cost: bool | None = None
    simplified_work_order: bool | None = None
    days_before_pm_notification: int | None = Field(default=None, ge=0)
    auto_assign_requests: bool | None = None
