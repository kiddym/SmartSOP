"""User management schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserStatus


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    role_id: str | None = None
    phone: str | None = Field(default=None, max_length=40)
    job_title: str | None = Field(default=None, max_length=128)
    rate: Decimal | None = Field(default=None, ge=0)
    avatar_url: str | None = Field(default=None, max_length=512)


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    role_id: str | None = None
    status: UserStatus | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    phone: str | None = Field(default=None, max_length=40)
    job_title: str | None = Field(default=None, max_length=128)
    rate: Decimal | None = Field(default=None, ge=0)
    avatar_url: str | None = Field(default=None, max_length=512)


class SelfProfileUpdate(BaseModel):
    """Self-service profile edit. Excludes role_id/status/rate (admin-only)."""

    model_config = ConfigDict(extra="ignore")
    name: str | None = Field(default=None, min_length=1, max_length=128)
    phone: str | None = Field(default=None, max_length=40)
    job_title: str | None = Field(default=None, max_length=128)
    avatar_url: str | None = Field(default=None, max_length=512)
    locale: str | None = Field(default=None, max_length=16)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: EmailStr
    name: str
    status: UserStatus
    role_id: str | None = None
    locale: str
    phone: str | None = None
    job_title: str | None = None
    rate: Decimal | None = None
    avatar_url: str | None = None
    last_login_at: datetime | None = None
    created_at: datetime
