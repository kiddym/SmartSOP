"""Permission-code registry + built-in role defaults.

Phase 0 declares only platform-layer codes. Later phases append module codes
here; built-in role default sets get extended accordingly.
"""
from __future__ import annotations

USER_CREATE = "user.create"
USER_VIEW = "user.view"
USER_EDIT = "user.edit"
USER_DELETE = "user.delete"
ROLE_VIEW = "role.view"
ROLE_MANAGE = "role.manage"
COMPANY_SETTINGS = "company.settings"

ALL_PERMISSIONS: list[str] = [
    USER_CREATE, USER_VIEW, USER_EDIT, USER_DELETE,
    ROLE_VIEW, ROLE_MANAGE, COMPANY_SETTINGS,
]

BUILTIN_ROLES: list[dict] = [
    {"code": "super_admin", "name": "超级管理员", "permissions": list(ALL_PERMISSIONS)},
    {"code": "admin", "name": "管理员", "permissions": [
        USER_CREATE, USER_VIEW, USER_EDIT, USER_DELETE,
        ROLE_VIEW, ROLE_MANAGE, COMPANY_SETTINGS]},
    {"code": "technician", "name": "技术员", "permissions": [USER_VIEW, ROLE_VIEW]},
    {"code": "viewer", "name": "只读", "permissions": [
        c for c in ALL_PERMISSIONS if c.endswith(".view")]},
]


def effective_codes(role_code: str, stored_codes: list[str]) -> set[str]:
    """super_admin is an implicit wildcard over ALL_PERMISSIONS."""
    if role_code == "super_admin":
        return set(ALL_PERMISSIONS)
    return set(stored_codes)
