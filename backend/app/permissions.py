"""Permission-code registry + built-in role defaults.

Phase 0 declares platform-layer codes; Phase 1A adds maintenance base-domain
codes (location/asset/asset_category/team). Later phases append more here and
extend the built-in role default sets accordingly.
"""

from __future__ import annotations

from typing import Any

# --- 平台层（Phase 0）---
USER_CREATE = "user.create"
USER_VIEW = "user.view"
USER_EDIT = "user.edit"
USER_DELETE = "user.delete"
ROLE_VIEW = "role.view"
ROLE_MANAGE = "role.manage"
COMPANY_SETTINGS = "company.settings"
CURRENCY_MANAGE = "currency.manage"

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

# --- 维修请求（Phase 2A）---
REQUEST_VIEW = "request.view"
REQUEST_CREATE = "request.create"
REQUEST_CANCEL = "request.cancel"
REQUEST_DELETE = "request.delete"
REQUEST_APPROVE = "request.approve"

# --- 预防性维护（Phase 2B）---
PREVENTIVE_MAINTENANCE_VIEW = "preventive_maintenance.view"
PREVENTIVE_MAINTENANCE_CREATE = "preventive_maintenance.create"
PREVENTIVE_MAINTENANCE_EDIT = "preventive_maintenance.edit"
PREVENTIVE_MAINTENANCE_DELETE = "preventive_maintenance.delete"

# --- 计量（Phase 2C）---
METER_VIEW = "meter.view"
METER_CREATE = "meter.create"
METER_EDIT = "meter.edit"
METER_DELETE = "meter.delete"
READING_VIEW = "reading.view"
READING_CREATE = "reading.create"

# --- 库存（Phase 3A）---
PART_VIEW = "part.view"
PART_CREATE = "part.create"
PART_EDIT = "part.edit"
PART_DELETE = "part.delete"
PART_CONSUME = "part.consume"
PART_CATEGORY_VIEW = "part_category.view"
PART_CATEGORY_MANAGE = "part_category.manage"

# --- 供应商 / 客户 / 成本分类（Phase 3B）---
VENDOR_VIEW = "vendor.view"
VENDOR_CREATE = "vendor.create"
VENDOR_EDIT = "vendor.edit"
VENDOR_DELETE = "vendor.delete"
CUSTOMER_VIEW = "customer.view"
CUSTOMER_CREATE = "customer.create"
CUSTOMER_EDIT = "customer.edit"
CUSTOMER_DELETE = "customer.delete"
COST_CATEGORY_VIEW = "cost_category.view"
COST_CATEGORY_MANAGE = "cost_category.manage"

# --- 工时分类（2A）---
TIME_CATEGORY_VIEW = "time_category.view"
TIME_CATEGORY_MANAGE = "time_category.manage"

# --- 采购单（Phase 3C）---
PURCHASE_ORDER_VIEW = "purchase_order.view"
PURCHASE_ORDER_CREATE = "purchase_order.create"
PURCHASE_ORDER_EDIT = "purchase_order.edit"
PURCHASE_ORDER_DELETE = "purchase_order.delete"
PURCHASE_ORDER_APPROVE = "purchase_order.approve"

# --- 采购单分类（库存补全 T5）---
PURCHASE_ORDER_CATEGORY_VIEW = "purchase_order_category.view"
PURCHASE_ORDER_CATEGORY_MANAGE = "purchase_order_category.manage"

# --- 分析与报表（Phase 4）---
ANALYTICS_VIEW = "analytics.view"

_PLATFORM = [
    USER_CREATE,
    USER_VIEW,
    USER_EDIT,
    USER_DELETE,
    ROLE_VIEW,
    ROLE_MANAGE,
    COMPANY_SETTINGS,
    CURRENCY_MANAGE,
]
_BASE_DOMAIN = [
    LOCATION_VIEW,
    LOCATION_CREATE,
    LOCATION_EDIT,
    LOCATION_DELETE,
    ASSET_VIEW,
    ASSET_CREATE,
    ASSET_EDIT,
    ASSET_DELETE,
    ASSET_CATEGORY_VIEW,
    ASSET_CATEGORY_MANAGE,
    TEAM_VIEW,
    TEAM_MANAGE,
]
_WORKORDER = [
    WORK_ORDER_VIEW,
    WORK_ORDER_CREATE,
    WORK_ORDER_EDIT,
    WORK_ORDER_DELETE,
    WORK_ORDER_EXECUTE,
]
_REQUEST = [
    REQUEST_VIEW,
    REQUEST_CREATE,
    REQUEST_CANCEL,
    REQUEST_DELETE,
    REQUEST_APPROVE,
]
_PREVENTIVE_MAINTENANCE = [
    PREVENTIVE_MAINTENANCE_VIEW,
    PREVENTIVE_MAINTENANCE_CREATE,
    PREVENTIVE_MAINTENANCE_EDIT,
    PREVENTIVE_MAINTENANCE_DELETE,
]
_METER = [METER_VIEW, METER_CREATE, METER_EDIT, METER_DELETE]
_READING = [READING_VIEW, READING_CREATE]
_PART = [PART_VIEW, PART_CREATE, PART_EDIT, PART_DELETE, PART_CONSUME]
_PART_CATEGORY = [PART_CATEGORY_VIEW, PART_CATEGORY_MANAGE]
_VENDOR = [VENDOR_VIEW, VENDOR_CREATE, VENDOR_EDIT, VENDOR_DELETE]
_CUSTOMER = [CUSTOMER_VIEW, CUSTOMER_CREATE, CUSTOMER_EDIT, CUSTOMER_DELETE]
_COST_CATEGORY = [COST_CATEGORY_VIEW, COST_CATEGORY_MANAGE]
_TIME_CATEGORY = [TIME_CATEGORY_VIEW, TIME_CATEGORY_MANAGE]
_PURCHASE_ORDER = [
    PURCHASE_ORDER_VIEW,
    PURCHASE_ORDER_CREATE,
    PURCHASE_ORDER_EDIT,
    PURCHASE_ORDER_DELETE,
    PURCHASE_ORDER_APPROVE,
]
_PURCHASE_ORDER_CATEGORY = [PURCHASE_ORDER_CATEGORY_VIEW, PURCHASE_ORDER_CATEGORY_MANAGE]
_ANALYTICS = [ANALYTICS_VIEW]

ALL_PERMISSIONS: list[str] = (
    _PLATFORM
    + _BASE_DOMAIN
    + _WORKORDER
    + _REQUEST
    + _PREVENTIVE_MAINTENANCE
    + _METER
    + _READING
    + _PART
    + _PART_CATEGORY
    + _VENDOR
    + _CUSTOMER
    + _COST_CATEGORY
    + _TIME_CATEGORY
    + _PURCHASE_ORDER
    + _PURCHASE_ORDER_CATEGORY
    + _ANALYTICS
)

BUILTIN_ROLES: list[dict[str, Any]] = [
    {"code": "super_admin", "name": "超级管理员", "permissions": list(ALL_PERMISSIONS)},
    {"code": "admin", "name": "管理员", "permissions": list(ALL_PERMISSIONS)},
    {
        "code": "technician",
        "name": "技术员",
        "permissions": [
            USER_VIEW,
            ROLE_VIEW,
            LOCATION_VIEW,
            ASSET_VIEW,
            ASSET_EDIT,
            ASSET_CATEGORY_VIEW,
            TEAM_VIEW,
            WORK_ORDER_VIEW,
            WORK_ORDER_EXECUTE,
            WORK_ORDER_EDIT,
            REQUEST_VIEW,
            REQUEST_CREATE,
            PREVENTIVE_MAINTENANCE_VIEW,
            METER_VIEW,
            READING_VIEW,
            READING_CREATE,
            PART_VIEW,
            PART_CONSUME,
            PART_CATEGORY_VIEW,
            VENDOR_VIEW,
            CUSTOMER_VIEW,
            COST_CATEGORY_VIEW,
            TIME_CATEGORY_VIEW,
            PURCHASE_ORDER_VIEW,
            PURCHASE_ORDER_CATEGORY_VIEW,
        ],
    },
    {
        "code": "viewer",
        "name": "只读",
        "permissions": [c for c in ALL_PERMISSIONS if c.endswith(".view")],
    },
    {
        "code": "requester",
        "name": "报修人",
        "permissions": [
            REQUEST_VIEW,
            REQUEST_CREATE,
        ],
    },
]


def effective_codes(role_code: str, stored_codes: list[str]) -> set[str]:
    """super_admin is an implicit wildcard over ALL_PERMISSIONS."""
    if role_code == "super_admin":
        return set(ALL_PERMISSIONS)
    return set(stored_codes)
