"""Permission-code registry + built-in role defaults.

Phase 0 declares platform-layer codes; Phase 1A adds maintenance base-domain
codes (location/asset/asset_category/team). Later phases append more here and
extend the built-in role default sets accordingly.
"""
from __future__ import annotations

# --- 平台层（Phase 0）---
USER_CREATE = "user.create"
USER_VIEW = "user.view"
USER_EDIT = "user.edit"
USER_DELETE = "user.delete"
ROLE_VIEW = "role.view"
ROLE_MANAGE = "role.manage"
COMPANY_SETTINGS = "company.settings"

# --- 维护基础域（Phase 1A）---
LOCATION_VIEW = "location.view"
LOCATION_CREATE = "location.create"
LOCATION_EDIT = "location.edit"
LOCATION_DELETE = "location.delete"
ASSET_VIEW = "asset.view"
ASSET_CREATE = "asset.create"
ASSET_EDIT = "asset.edit"
ASSET_DELETE = "asset.delete"
ASSET_CATEGORY_VIEW = "asset_category.view"
ASSET_CATEGORY_MANAGE = "asset_category.manage"
TEAM_VIEW = "team.view"
TEAM_MANAGE = "team.manage"

# --- 维护闭环（Phase 1B）---
WORK_ORDER_VIEW = "work_order.view"
WORK_ORDER_CREATE = "work_order.create"
WORK_ORDER_EDIT = "work_order.edit"
WORK_ORDER_DELETE = "work_order.delete"
WORK_ORDER_EXECUTE = "work_order.execute"

_PLATFORM = [
    USER_CREATE, USER_VIEW, USER_EDIT, USER_DELETE,
    ROLE_VIEW, ROLE_MANAGE, COMPANY_SETTINGS,
]
_BASE_DOMAIN = [
    LOCATION_VIEW, LOCATION_CREATE, LOCATION_EDIT, LOCATION_DELETE,
    ASSET_VIEW, ASSET_CREATE, ASSET_EDIT, ASSET_DELETE,
    ASSET_CATEGORY_VIEW, ASSET_CATEGORY_MANAGE,
    TEAM_VIEW, TEAM_MANAGE,
]
_WORKORDER = [
    WORK_ORDER_VIEW, WORK_ORDER_CREATE, WORK_ORDER_EDIT,
    WORK_ORDER_DELETE, WORK_ORDER_EXECUTE,
]

ALL_PERMISSIONS: list[str] = _PLATFORM + _BASE_DOMAIN + _WORKORDER

BUILTIN_ROLES: list[dict] = [
    {"code": "super_admin", "name": "超级管理员", "permissions": list(ALL_PERMISSIONS)},
    {"code": "admin", "name": "管理员", "permissions": list(ALL_PERMISSIONS)},
    {"code": "technician", "name": "技术员", "permissions": [
        USER_VIEW, ROLE_VIEW,
        LOCATION_VIEW, ASSET_VIEW, ASSET_EDIT, ASSET_CATEGORY_VIEW, TEAM_VIEW,
        WORK_ORDER_VIEW, WORK_ORDER_EXECUTE, WORK_ORDER_EDIT,
    ]},
    {"code": "viewer", "name": "只读", "permissions": [
        c for c in ALL_PERMISSIONS if c.endswith(".view")]},
]


def effective_codes(role_code: str, stored_codes: list[str]) -> set[str]:
    """super_admin is an implicit wildcard over ALL_PERMISSIONS."""
    if role_code == "super_admin":
        return set(ALL_PERMISSIONS)
    return set(stored_codes)
