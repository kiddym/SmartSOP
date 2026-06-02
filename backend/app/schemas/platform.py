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
