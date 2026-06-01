"""Role management schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.permissions import ALL_PERMISSIONS


def _validate(codes: list[str]) -> list[str]:
    unknown = [c for c in codes if c not in ALL_PERMISSIONS]
    if unknown:
        raise ValueError(f"未知权限点: {unknown}")
    return codes


class RoleCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    permissions: list[str] = []

    @field_validator("permissions")
    @classmethod
    def _check(cls, v: list[str]) -> list[str]:
        return _validate(v)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    permissions: list[str] | None = None

    @field_validator("permissions")
    @classmethod
    def _check(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else _validate(v)


class RoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    code: str
    name: str
    is_builtin: bool
    permissions: list[str]
