"""Auth request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    company_slug: str | None = None  # disambiguates email across tenants


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class CurrentUser(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    email: EmailStr
    name: str
    company_id: str
    role_code: str | None = None
    permissions: list[str] = []
    email_verified: bool = False


class ForgotPasswordRequest(BaseModel):
    email: EmailStr
    company_slug: str | None = None


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=128)


class SwitchableAccount(BaseModel):
    """可切换进的目标公司 + 目标成员账户身份。"""

    company_id: str
    company_name: str
    company_slug: str
    user_id: str


class SwitchAccountRequest(BaseModel):
    company_id: str


class VerifyEmailRequest(BaseModel):
    token: str
