"""User management schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserStatus


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    role_id: str | None = None


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    role_id: str | None = None
    status: UserStatus | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: EmailStr
    name: str
    status: UserStatus
    role_id: str | None = None
    locale: str
    last_login_at: datetime | None = None
    created_at: datetime
