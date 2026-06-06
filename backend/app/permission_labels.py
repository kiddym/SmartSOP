"""权限 code 的中文 label 与分组，供前端角色表单渲染分域勾选框。

与 ``app.permissions`` 同源：``PERMISSION_GROUPS`` 的并集恰为 ``ALL_PERMISSIONS``，
``PERMISSION_LABELS`` 覆盖每一个 code。模块末尾做覆盖自检，漂移即报错。
"""

from __future__ import annotations

from app import permissions as perms

# （中文组名, 该组 code 列表）；顺序即前端展示顺序。
PERMISSION_GROUPS: list[tuple[str, list[str]]] = [
    ("平台", perms._PLATFORM),
    ("主数据", perms._BASE_DOMAIN),
    ("工单", perms._WORKORDER),
    ("工单分类", perms._WORK_ORDER_CATEGORY),
    ("工时分类", perms._TIME_CATEGORY),
    ("请求", perms._REQUEST),
    ("预防性维护", perms._PREVENTIVE_MAINTENANCE),
    ("计量", perms._METER + perms._READING + perms._METER_CATEGORY),
    ("备件", perms._PART + perms._PART_CATEGORY),
    ("供应商客户", perms._VENDOR + perms._CUSTOMER),
    ("采购", perms._PURCHASE_ORDER + perms._PURCHASE_ORDER_CATEGORY),
    ("成本分类", perms._COST_CATEGORY),
    ("分析", perms._ANALYTICS),
    ("工作流", perms._WORKFLOW),
]

# 每个 code → 中文 label（「<实体>-<动作>」）。
PERMISSION_LABELS: dict[str, str] = {
    # 平台
    perms.USER_CREATE: "用户-创建",
    perms.USER_VIEW: "用户-查看",
    perms.USER_EDIT: "用户-编辑",
    perms.USER_DELETE: "用户-删除",
    perms.ROLE_VIEW: "角色-查看",
    perms.ROLE_MANAGE: "角色-管理",
    perms.COMPANY_SETTINGS: "公司设置",
    perms.CURRENCY_MANAGE: "货币-管理",
    perms.BILLING_MANAGE: "计费-管理",
    # 主数据
    perms.LOCATION_VIEW: "位置-查看",
    perms.LOCATION_CREATE: "位置-创建",
    perms.LOCATION_EDIT: "位置-编辑",
    perms.LOCATION_DELETE: "位置-删除",
    perms.ASSET_VIEW: "资产-查看",
    perms.ASSET_CREATE: "资产-创建",
    perms.ASSET_EDIT: "资产-编辑",
    perms.ASSET_DELETE: "资产-删除",
    perms.ASSET_CATEGORY_VIEW: "资产分类-查看",
    perms.ASSET_CATEGORY_MANAGE: "资产分类-管理",
    perms.TEAM_VIEW: "团队-查看",
    perms.TEAM_MANAGE: "团队-管理",
    # 工单
    perms.WORK_ORDER_VIEW: "工单-查看",
    perms.WORK_ORDER_CREATE: "工单-创建",
    perms.WORK_ORDER_EDIT: "工单-编辑",
    perms.WORK_ORDER_DELETE: "工单-删除",
    perms.WORK_ORDER_EXECUTE: "工单-执行",
    # 工单分类
    perms.WORK_ORDER_CATEGORY_VIEW: "工单分类-查看",
    perms.WORK_ORDER_CATEGORY_MANAGE: "工单分类-管理",
    # 工时分类
    perms.TIME_CATEGORY_VIEW: "工时分类-查看",
    perms.TIME_CATEGORY_MANAGE: "工时分类-管理",
    # 请求
    perms.REQUEST_VIEW: "请求-查看",
    perms.REQUEST_CREATE: "请求-创建",
    perms.REQUEST_CANCEL: "请求-取消",
    perms.REQUEST_DELETE: "请求-删除",
    perms.REQUEST_APPROVE: "请求-审批",
    # 预防性维护
    perms.PREVENTIVE_MAINTENANCE_VIEW: "预防性维护-查看",
    perms.PREVENTIVE_MAINTENANCE_CREATE: "预防性维护-创建",
    perms.PREVENTIVE_MAINTENANCE_EDIT: "预防性维护-编辑",
    perms.PREVENTIVE_MAINTENANCE_DELETE: "预防性维护-删除",
    # 计量
    perms.METER_VIEW: "计量点-查看",
    perms.METER_CREATE: "计量点-创建",
    perms.METER_EDIT: "计量点-编辑",
    perms.METER_DELETE: "计量点-删除",
    perms.READING_VIEW: "读数-查看",
    perms.READING_CREATE: "读数-录入",
    perms.METER_CATEGORY_VIEW: "计量分类-查看",
    perms.METER_CATEGORY_MANAGE: "计量分类-管理",
    # 备件
    perms.PART_VIEW: "备件-查看",
    perms.PART_CREATE: "备件-创建",
    perms.PART_EDIT: "备件-编辑",
    perms.PART_DELETE: "备件-删除",
    perms.PART_CONSUME: "备件-领用",
    perms.PART_CATEGORY_VIEW: "备件分类-查看",
    perms.PART_CATEGORY_MANAGE: "备件分类-管理",
    # 供应商客户
    perms.VENDOR_VIEW: "供应商-查看",
    perms.VENDOR_CREATE: "供应商-创建",
    perms.VENDOR_EDIT: "供应商-编辑",
    perms.VENDOR_DELETE: "供应商-删除",
    perms.CUSTOMER_VIEW: "客户-查看",
    perms.CUSTOMER_CREATE: "客户-创建",
    perms.CUSTOMER_EDIT: "客户-编辑",
    perms.CUSTOMER_DELETE: "客户-删除",
    # 采购
    perms.PURCHASE_ORDER_VIEW: "采购单-查看",
    perms.PURCHASE_ORDER_CREATE: "采购单-创建",
    perms.PURCHASE_ORDER_EDIT: "采购单-编辑",
    perms.PURCHASE_ORDER_DELETE: "采购单-删除",
    perms.PURCHASE_ORDER_APPROVE: "采购单-审批",
    perms.PURCHASE_ORDER_CATEGORY_VIEW: "采购单分类-查看",
    perms.PURCHASE_ORDER_CATEGORY_MANAGE: "采购单分类-管理",
    # 成本分类
    perms.COST_CATEGORY_VIEW: "成本分类-查看",
    perms.COST_CATEGORY_MANAGE: "成本分类-管理",
    # 分析
    perms.ANALYTICS_VIEW: "分析-查看",
    # 工作流
    perms.WORKFLOW_VIEW: "工作流-查看",
    perms.WORKFLOW_MANAGE: "工作流-管理",
}

# 自检：分组并集 == ALL_PERMISSIONS，且 label 全覆盖（防止 permissions.py 漂移）。
_grouped = [c for _, codes in PERMISSION_GROUPS for c in codes]
assert set(_grouped) == set(perms.ALL_PERMISSIONS), "PERMISSION_GROUPS 与 ALL_PERMISSIONS 不一致"
assert len(_grouped) == len(perms.ALL_PERMISSIONS), "PERMISSION_GROUPS 存在重复 code"
assert set(PERMISSION_LABELS) == set(perms.ALL_PERMISSIONS), "PERMISSION_LABELS 未覆盖全部 code"
