from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


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
