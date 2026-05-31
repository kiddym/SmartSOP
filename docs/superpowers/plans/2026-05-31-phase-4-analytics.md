# Phase 4 分析与报表（Analytics & Reports）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在已完成的 Phase 0–3C 数据之上提供后端**只读分析 API**：4 组运营仪表盘（工单合规吞吐 / 成本 / 资产可靠性 / 库存）+ 每盘 CSV 导出 + `analytics.view` RBAC，零新表零迁移。

**Architecture:** 方案 A 请求时实时聚合。新建 `app/services/analytics/` 包（每盘一聚焦模块）+ `app/schemas/analytics.py` + `app/routers/analytics.py`。租户隔离沿用既有 `with_loader_criteria` ORM 事件（service 不显式传 company_id，靠租户上下文作用域）。**跨方言安全策略**：计数/分组键用 SQL，但**所有时长（小时差）与金额（Decimal 乘加）一律取列入 Python 计算**（SQLite 下 `func.sum/min` 会丢失 Numeric/DATETIME6 类型处理器，与既有 line_total 同策略）。

**Tech Stack:** FastAPI · SQLAlchemy 2.0 (sync) · Pydantic v2 · SQLite(测试)/MySQL(生产) · pytest。

**全局约定（每个 task 都遵守）：**
- 跑 python/pytest 前：`cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate`
- 跑测试前清缓存：`find . -name __pycache__ -type d -exec rm -rf {} + ; rm -rf .pytest_cache` 且加 `PYTHONDONTWRITEBYTECODE=1`
- 共享文件（`main.py`/`permissions.py`）一律用 Edit 精确替换，禁 sed/re.sub；插入前先 Read 定位真实锚点（3B/3C 已留下 vendor/customer/cost_category/purchase_order 锚点，Phase 4 在其后追加）。
- 提交 message 末行：`Co-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>`（注意是 "Claude Opus 4.5"，不是 4.8）
- 新文件务必 `git add` 后再提交。**只精确 `git add` 本 task 涉及的文件，禁 `git add .` / `git add -A`**（工作树可能有其他会话的游离改动，勿误纳）。
- 复用既有签名：`bad_request(code,msg)`/`not_found(code,msg)`（`app.errors`，raise HTTPException）；`app.deps.get_db`、`require_permission(code)`；`app.models.base.utcnow`、`DATETIME6`。
- 基线：全量 pytest 945 passed，alembic 单 head `phase3c_purchase_order`。**本期零新表零迁移**，head 不变。
- 设计依据：`docs/superpowers/specs/2026-05-31-phase-4-analytics-design.md`。

**测试数据策略：**
- **单测**（service 层）用 `db` fixture 直插 ORM 行，统一 `company_id="co-1"`（无租户中间件→租户事件 no-op→service 见全部种子行）；时间字段显式传（如 `created_at=datetime(...)`）以确定性命中/落窗。SQLite 默认 FK 关闭，无需建 `tb_company` 行。
- **API 测**用 `client` + `db`（二者共享同一 in-memory engine，StaticPool 单连接，`db` 提交的行对 `client` 请求可见）。先 register 取 token，再用 `db` 按该公司 `company_id` 直插种子行（必须显式设 `company_id`，因 `db` fixture 无租户上下文）。公司 id 经 `select(Company).where(Company.slug==...)` 取。

---

## Task 1: RBAC — analytics.view 权限码 + 契约测试

**Files:**
- Modify: `backend/app/permissions.py`
- Test: `backend/tests/test_permissions_phase4.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_permissions_phase4.py`:
```python
from app import permissions as perms


def test_analytics_view_registered():
    assert "analytics.view" in perms.ALL_PERMISSIONS


def test_no_duplicate_codes():
    assert len(perms.ALL_PERMISSIONS) == len(set(perms.ALL_PERMISSIONS))


def test_super_admin_and_admin_have_analytics():
    assert "analytics.view" in perms.effective_codes("super_admin", [])
    admin = next(r for r in perms.BUILTIN_ROLES if r["code"] == "admin")
    assert "analytics.view" in admin["permissions"]


def test_viewer_includes_analytics_view():
    viewer = next(r for r in perms.BUILTIN_ROLES if r["code"] == "viewer")
    assert "analytics.view" in viewer["permissions"]


def test_technician_excluded_from_analytics():
    tech = next(r for r in perms.BUILTIN_ROLES if r["code"] == "technician")
    assert "analytics.view" not in tech["permissions"]


def test_requester_unchanged():
    requester = next(r for r in perms.BUILTIN_ROLES if r["code"] == "requester")
    assert set(requester["permissions"]) == {"request.view", "request.create"}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_permissions_phase4.py -q`
Expected: FAIL（analytics.view 未注册）

- [ ] **Step 3: 改 `app/permissions.py`**

先 Read 文件。在 `PURCHASE_ORDER_APPROVE = "purchase_order.approve"` 行之后插入：
```python

# --- 分析与报表（Phase 4）---
ANALYTICS_VIEW = "analytics.view"
```
在 `_PURCHASE_ORDER = [...]` 块（以 `]` 结尾）之后插入：
```python
_ANALYTICS = [ANALYTICS_VIEW]
```
把 `ALL_PERMISSIONS` 聚合表达式末尾追加 `+ _ANALYTICS`（仅在 `+ _PURCHASE_ORDER` 之后追加，不丢任何既有组）：
```python
ALL_PERMISSIONS: list[str] = (
    _PLATFORM + _BASE_DOMAIN + _WORKORDER + _REQUEST + _PREVENTIVE_MAINTENANCE
    + _METER + _READING + _PART + _PART_CATEGORY
    + _VENDOR + _CUSTOMER + _COST_CATEGORY
    + _PURCHASE_ORDER
    + _ANALYTICS
)
```
（admin/super_admin 自动含全部；viewer 经 `.endswith(".view")` 自动含 analytics.view；technician 不在其显式列表故不含；requester 不变。无需改任何角色列表。）

- [ ] **Step 4: 跑测试确认通过 + 既有契约不破**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_permissions_phase4.py tests/test_permissions_phase3c.py -q && PYTHONDONTWRITEBYTECODE=1 pytest tests/ -q -k "permission or roles or auth_service"`
Expected: PASS（新测 + 既有契约仍绿）

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/permissions.py backend/tests/test_permissions_phase4.py
git commit -m "$(printf 'feat(phase-4): add analytics.view permission + role defaults\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 2: analytics 包 + `_common.py` 纯函数（窗口/时长/区间裁剪）

**Files:**
- Create: `backend/app/services/analytics/__init__.py`（空文件）
- Create: `backend/app/services/analytics/_common.py`
- Test: `backend/tests/unit/test_analytics_common.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_analytics_common.py`:
```python
from datetime import date, datetime, timedelta

from app.services.analytics._common import (
    clip_interval,
    hours_between,
    resolve_window,
)


def test_resolve_window_explicit_inclusive_end():
    start, end_excl, df, dt = resolve_window(date(2026, 1, 1), date(2026, 1, 31))
    assert start == datetime(2026, 1, 1, 0, 0, 0)
    assert end_excl == datetime(2026, 2, 1, 0, 0, 0)  # date_to 含当日 -> +1 天开区间
    assert df == date(2026, 1, 1) and dt == date(2026, 1, 31)


def test_resolve_window_defaults_last_90_days():
    start, end_excl, df, dt = resolve_window(None, None)
    assert (dt - df) == timedelta(days=90)
    assert end_excl == datetime(dt.year, dt.month, dt.day) + timedelta(days=1)


def test_resolve_window_only_from():
    start, end_excl, df, dt = resolve_window(date(2026, 3, 1), None)
    assert df == date(2026, 3, 1)
    assert dt >= df


def test_hours_between():
    assert hours_between(datetime(2026, 1, 1, 0), datetime(2026, 1, 1, 6)) == 6.0
    assert hours_between(datetime(2026, 1, 1, 0), datetime(2026, 1, 2, 0)) == 24.0


def test_clip_interval_fully_inside():
    win_s, win_e = datetime(2026, 1, 1), datetime(2026, 2, 1)
    assert clip_interval(datetime(2026, 1, 10), datetime(2026, 1, 12), win_s, win_e) == (
        datetime(2026, 1, 10), datetime(2026, 1, 12))


def test_clip_interval_ongoing_uses_window_end():
    win_s, win_e = datetime(2026, 1, 1), datetime(2026, 2, 1)
    assert clip_interval(datetime(2026, 1, 20), None, win_s, win_e) == (
        datetime(2026, 1, 20), datetime(2026, 2, 1))


def test_clip_interval_clamped_to_window():
    win_s, win_e = datetime(2026, 1, 10), datetime(2026, 1, 20)
    assert clip_interval(datetime(2026, 1, 5), datetime(2026, 1, 25), win_s, win_e) == (
        datetime(2026, 1, 10), datetime(2026, 1, 20))


def test_clip_interval_no_overlap_returns_none():
    win_s, win_e = datetime(2026, 1, 10), datetime(2026, 1, 20)
    assert clip_interval(datetime(2026, 1, 1), datetime(2026, 1, 5), win_s, win_e) is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_analytics_common.py -q`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 写实现**

`backend/app/services/analytics/__init__.py`:
```python
"""Phase 4 分析聚合服务（只读，请求时实时聚合）。"""
```

`backend/app/services/analytics/_common.py`:
```python
"""分析服务共享纯函数：时间窗口解析、时长、停机区间裁剪。

跨方言安全：所有时长用 Python timedelta 计算（不用 SQL 日期函数）。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from app.models.base import utcnow

DEFAULT_WINDOW_DAYS = 90


def resolve_window(
    date_from: date | None, date_to: date | None
) -> tuple[datetime, datetime, date, date]:
    """把 [date_from, date_to]（含端点）解析为半开 datetime 边界 [start, end_excl)。

    两者都省略时默认最近 DEFAULT_WINDOW_DAYS 天（以今日为含端点的窗末）。
    返回 (start, end_excl, date_from, date_to)。
    """
    today = utcnow().date()
    if date_to is None:
        date_to = today
    if date_from is None:
        date_from = date_to - timedelta(days=DEFAULT_WINDOW_DAYS)
    start = datetime(date_from.year, date_from.month, date_from.day)
    end_excl = datetime(date_to.year, date_to.month, date_to.day) + timedelta(days=1)
    return start, end_excl, date_from, date_to


def hours_between(start: datetime, end: datetime) -> float:
    return (end - start).total_seconds() / 3600.0


def clip_interval(
    start: datetime, end: datetime | None, win_start: datetime, win_end: datetime
) -> tuple[datetime, datetime] | None:
    """把停机区间 [start, end) 裁剪到窗口 [win_start, win_end)。

    end 为 None 表示进行中，按 win_end 处理。无重叠返回 None。
    """
    eff_end = end if end is not None else win_end
    lo = max(start, win_start)
    hi = min(eff_end, win_end)
    if hi <= lo:
        return None
    return lo, hi
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_analytics_common.py -q`
Expected: PASS（8 passed）

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/services/analytics/__init__.py backend/app/services/analytics/_common.py backend/tests/unit/test_analytics_common.py
git commit -m "$(printf 'feat(phase-4): add analytics common window/duration helpers\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 3: Pydantic 响应 schema（单文件 analytics.py）

**Files:**
- Create: `backend/app/schemas/analytics.py`
- Test: `backend/tests/unit/test_analytics_schemas.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_analytics_schemas.py`:
```python
from datetime import date
from decimal import Decimal

from app.schemas.analytics import (
    AssetReliabilityAnalytics,
    CostAnalytics,
    InventoryAnalytics,
    WorkOrderAnalytics,
)


def test_work_order_analytics_shape():
    m = WorkOrderAnalytics(
        date_from=date(2026, 1, 1), date_to=date(2026, 1, 31), total=2,
        by_status={"OPEN": 1, "COMPLETE": 1}, by_priority={"HIGH": 2},
        completed=1, completion_rate=0.5, overdue=0,
        avg_cycle_time_hours=12.0, avg_response_time_hours=None,
    )
    assert m.completion_rate == 0.5 and m.avg_response_time_hours is None


def test_cost_analytics_decimal():
    m = CostAnalytics(
        date_from=date(2026, 1, 1), date_to=date(2026, 1, 31),
        parts_consumption_cost=Decimal("6.0000"),
        consumption_by_part=[{"part_id": "p1", "custom_id": "PRT1", "name": "x",
                              "qty": Decimal("3"), "cost": Decimal("6")}],
        consumption_by_asset=[{"asset_id": None, "cost": Decimal("6")}],
        po_spend_approved=Decimal("0"), po_spend_by_vendor=[],
    )
    assert m.consumption_by_part[0].cost == Decimal("6")


def test_asset_reliability_nullable_mtbf():
    m = AssetReliabilityAnalytics(
        date_from=date(2026, 1, 1), date_to=date(2026, 1, 31), window_hours=744.0,
        assets=[{"asset_id": "a1", "custom_id": "AST1", "name": "pump",
                 "availability_pct": 100.0, "downtime_count": 0,
                 "total_downtime_hours": 0.0, "mttr_hours": None, "mtbf_hours": None}],
        fleet_availability_pct=100.0, fleet_total_downtime_hours=0.0,
        fleet_mttr_hours=None, fleet_mtbf_hours=None,
    )
    assert m.assets[0].mtbf_hours is None


def test_inventory_analytics_shape():
    m = InventoryAnalytics(
        total_inventory_value=Decimal("100"), inventory_value_by_category=[],
        low_stock_count=1,
        low_stock_items=[{"part_id": "p1", "custom_id": "PRT1", "name": "x",
                          "quantity": Decimal("1"), "min_quantity": Decimal("5"),
                          "shortfall": Decimal("4")}],
        top_consumed_parts=[],
    )
    assert m.low_stock_items[0].shortfall == Decimal("4")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_analytics_schemas.py -q`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 写实现**

`backend/app/schemas/analytics.py`:
```python
"""分析仪表盘响应 schema（Phase 4，只读）。"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class WorkOrderAnalytics(BaseModel):
    date_from: date
    date_to: date
    total: int
    by_status: dict[str, int]
    by_priority: dict[str, int]
    completed: int
    completion_rate: float
    overdue: int
    avg_cycle_time_hours: float | None
    avg_response_time_hours: float | None


class PartCostRow(BaseModel):
    part_id: str
    custom_id: str
    name: str
    qty: Decimal
    cost: Decimal


class AssetCostRow(BaseModel):
    asset_id: str | None
    cost: Decimal


class VendorSpendRow(BaseModel):
    vendor_id: str
    spend: Decimal


class CostAnalytics(BaseModel):
    date_from: date
    date_to: date
    parts_consumption_cost: Decimal
    consumption_by_part: list[PartCostRow]
    consumption_by_asset: list[AssetCostRow]
    po_spend_approved: Decimal
    po_spend_by_vendor: list[VendorSpendRow]


class AssetReliabilityRow(BaseModel):
    asset_id: str
    custom_id: str
    name: str
    availability_pct: float
    downtime_count: int
    total_downtime_hours: float
    mttr_hours: float | None
    mtbf_hours: float | None


class AssetReliabilityAnalytics(BaseModel):
    date_from: date
    date_to: date
    window_hours: float
    assets: list[AssetReliabilityRow]
    fleet_availability_pct: float | None
    fleet_total_downtime_hours: float
    fleet_mttr_hours: float | None
    fleet_mtbf_hours: float | None


class CategoryValueRow(BaseModel):
    category_id: str | None
    name: str | None
    value: Decimal


class LowStockRow(BaseModel):
    part_id: str
    custom_id: str
    name: str
    quantity: Decimal
    min_quantity: Decimal
    shortfall: Decimal


class TopConsumedRow(BaseModel):
    part_id: str
    custom_id: str
    name: str
    qty: Decimal


class InventoryAnalytics(BaseModel):
    total_inventory_value: Decimal
    inventory_value_by_category: list[CategoryValueRow]
    low_stock_count: int
    low_stock_items: list[LowStockRow]
    top_consumed_parts: list[TopConsumedRow]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_analytics_schemas.py -q`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/schemas/analytics.py backend/tests/unit/test_analytics_schemas.py
git commit -m "$(printf 'feat(phase-4): add analytics response schemas\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 4: 工单合规吞吐聚合 service

**Files:**
- Create: `backend/app/services/analytics/work_order_analytics.py`
- Test: `backend/tests/unit/test_analytics_work_order.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_analytics_work_order.py`:
```python
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.work_order import WorkOrder
from app.models.work_order_activity import WorkOrderActivity
from app.models.work_order_status import WorkOrderPriority, WorkOrderStatus
from app.services.analytics import work_order_analytics as svc

CO = "co-1"


def _wo(db, *, status=WorkOrderStatus.OPEN, priority=WorkOrderPriority.NONE,
        created, completed_at=None, due_date=None, asset_id=None, location_id=None,
        custom_id="WO000001"):
    wo = WorkOrder(custom_id=custom_id, title="t", status=status, priority=priority,
                   created_at=created, completed_at=completed_at, due_date=due_date,
                   asset_id=asset_id, location_id=location_id, company_id=CO)
    db.add(wo)
    db.commit()
    db.refresh(wo)
    return wo


def test_empty_window_zeroes(db: Session):
    r = svc.work_order_dashboard(db, date_from=date(2026, 1, 1), date_to=date(2026, 1, 31))
    assert r["total"] == 0 and r["completion_rate"] == 0.0
    assert r["avg_cycle_time_hours"] is None and r["avg_response_time_hours"] is None
    assert set(r["by_status"]) == {s.value for s in WorkOrderStatus}


def test_counts_and_completion_rate(db: Session):
    base = datetime(2026, 1, 10, 8)
    _wo(db, status=WorkOrderStatus.COMPLETE, priority=WorkOrderPriority.HIGH,
        created=base, completed_at=base + timedelta(hours=10), custom_id="WO1")
    _wo(db, status=WorkOrderStatus.OPEN, created=base, custom_id="WO2")
    r = svc.work_order_dashboard(db, date_from=date(2026, 1, 1), date_to=date(2026, 1, 31))
    assert r["total"] == 2 and r["completed"] == 1 and r["completion_rate"] == 0.5
    assert r["by_status"]["COMPLETE"] == 1 and r["by_status"]["OPEN"] == 1
    assert r["by_priority"]["HIGH"] == 1
    assert r["avg_cycle_time_hours"] == 10.0


def test_window_excludes_outside(db: Session):
    _wo(db, created=datetime(2025, 12, 1), custom_id="OLD")
    r = svc.work_order_dashboard(db, date_from=date(2026, 1, 1), date_to=date(2026, 1, 31))
    assert r["total"] == 0


def test_overdue_as_of_date_to(db: Session):
    base = datetime(2026, 1, 5)
    _wo(db, status=WorkOrderStatus.OPEN, created=base, due_date=date(2026, 1, 10), custom_id="A")
    _wo(db, status=WorkOrderStatus.COMPLETE, created=base, due_date=date(2026, 1, 10),
        completed_at=base, custom_id="B")  # 终态不算逾期
    r = svc.work_order_dashboard(db, date_from=date(2026, 1, 1), date_to=date(2026, 1, 31))
    assert r["overdue"] == 1


def test_response_time_from_first_in_progress(db: Session):
    base = datetime(2026, 1, 10, 8)
    wo = _wo(db, status=WorkOrderStatus.IN_PROGRESS, created=base, custom_id="R")
    db.add(WorkOrderActivity(work_order_id=wo.id, activity_type="STATUS_CHANGE",
                             to_status="IN_PROGRESS", created_at=base + timedelta(hours=2),
                             company_id=CO))
    db.add(WorkOrderActivity(work_order_id=wo.id, activity_type="STATUS_CHANGE",
                             to_status="IN_PROGRESS", created_at=base + timedelta(hours=5),
                             company_id=CO))  # 取最早一条
    db.commit()
    r = svc.work_order_dashboard(db, date_from=date(2026, 1, 1), date_to=date(2026, 1, 31))
    assert r["avg_response_time_hours"] == 2.0


def test_filter_by_asset(db: Session):
    base = datetime(2026, 1, 10)
    _wo(db, created=base, asset_id="a-1", custom_id="X")
    _wo(db, created=base, asset_id="a-2", custom_id="Y")
    r = svc.work_order_dashboard(db, date_from=date(2026, 1, 1), date_to=date(2026, 1, 31),
                                 asset_id="a-1")
    assert r["total"] == 1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_analytics_work_order.py -q`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 写实现**

`backend/app/services/analytics/work_order_analytics.py`:
```python
"""工单合规吞吐聚合（只读）。时长在 Python 计算以跨方言安全。"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.work_order import WorkOrder
from app.models.work_order_activity import WorkOrderActivity
from app.models.work_order_status import WorkOrderPriority, WorkOrderStatus
from app.services.analytics._common import hours_between, resolve_window


def work_order_dashboard(
    db: Session, *, date_from: date | None = None, date_to: date | None = None,
    asset_id: str | None = None, location_id: str | None = None,
) -> dict:
    start, end_excl, df, dt = resolve_window(date_from, date_to)
    stmt = select(WorkOrder).where(
        WorkOrder.is_active.is_(True),
        WorkOrder.created_at >= start,
        WorkOrder.created_at < end_excl,
    )
    if asset_id is not None:
        stmt = stmt.where(WorkOrder.asset_id == asset_id)
    if location_id is not None:
        stmt = stmt.where(WorkOrder.location_id == location_id)
    wos = list(db.execute(stmt).scalars().all())

    total = len(wos)
    by_status = {s.value: 0 for s in WorkOrderStatus}
    by_priority = {p.value: 0 for p in WorkOrderPriority}
    for wo in wos:
        by_status[wo.status.value] += 1
        by_priority[wo.priority.value] += 1
    completed = by_status[WorkOrderStatus.COMPLETE.value]
    completion_rate = round(completed / total, 4) if total else 0.0

    cycles = [
        hours_between(wo.created_at, wo.completed_at)
        for wo in wos
        if wo.status == WorkOrderStatus.COMPLETE and wo.completed_at is not None
    ]
    avg_cycle = round(sum(cycles) / len(cycles), 2) if cycles else None

    overdue = sum(
        1 for wo in wos
        if wo.due_date is not None and wo.due_date < dt
        and wo.status not in (WorkOrderStatus.COMPLETE, WorkOrderStatus.CANCELED)
    )

    # 首条 ->IN_PROGRESS 活动时间（取列入 Python 求 min，避免 SQLite func.min 丢类型）
    first_ip: dict[str, object] = {}
    wo_ids = [wo.id for wo in wos]
    if wo_ids:
        act_rows = db.execute(
            select(WorkOrderActivity.work_order_id, WorkOrderActivity.created_at).where(
                WorkOrderActivity.work_order_id.in_(wo_ids),
                WorkOrderActivity.to_status == WorkOrderStatus.IN_PROGRESS.value,
            )
        ).all()
        for wid, ts in act_rows:
            if wid not in first_ip or ts < first_ip[wid]:
                first_ip[wid] = ts
    resp = [hours_between(wo.created_at, first_ip[wo.id]) for wo in wos if wo.id in first_ip]
    avg_response = round(sum(resp) / len(resp), 2) if resp else None

    return {
        "date_from": df, "date_to": dt, "total": total,
        "by_status": by_status, "by_priority": by_priority,
        "completed": completed, "completion_rate": completion_rate,
        "overdue": overdue, "avg_cycle_time_hours": avg_cycle,
        "avg_response_time_hours": avg_response,
    }
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_analytics_work_order.py -q`
Expected: PASS（6 passed）

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/services/analytics/work_order_analytics.py backend/tests/unit/test_analytics_work_order.py
git commit -m "$(printf 'feat(phase-4): add work order analytics aggregation\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 5: 成本聚合 service（备件消耗 + PO 花费）

**Files:**
- Create: `backend/app/services/analytics/cost_analytics.py`
- Test: `backend/tests/unit/test_analytics_cost.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_analytics_cost.py`:
```python
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.part import Part
from app.models.purchase_order import PurchaseOrder, PurchaseOrderLine
from app.models.purchase_order_status import PurchaseOrderStatus
from app.models.part_consumption import PartConsumption
from app.models.work_order import WorkOrder
from app.services.analytics import cost_analytics as svc

CO = "co-1"


def _part(db, custom_id="PRT1", name="x"):
    p = Part(custom_id=custom_id, name=name, company_id=CO)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _wo(db, *, asset_id=None, custom_id="WO1"):
    wo = WorkOrder(custom_id=custom_id, title="t", asset_id=asset_id,
                   created_at=datetime(2026, 1, 5), company_id=CO)
    db.add(wo)
    db.commit()
    db.refresh(wo)
    return wo


def _consume(db, part, wo, qty, unit_cost, when):
    db.add(PartConsumption(part_id=part.id, work_order_id=wo.id,
                           quantity=Decimal(qty), unit_cost=Decimal(unit_cost),
                           consumed_at=when, company_id=CO))
    db.commit()


def test_empty_costs(db: Session):
    r = svc.cost_dashboard(db, date_from=date(2026, 1, 1), date_to=date(2026, 1, 31))
    assert r["parts_consumption_cost"] == Decimal("0")
    assert r["po_spend_approved"] == Decimal("0")
    assert r["consumption_by_part"] == [] and r["po_spend_by_vendor"] == []


def test_consumption_cost_and_breakdowns(db: Session):
    p1, p2 = _part(db, "PRT1"), _part(db, "PRT2")
    wo = _wo(db, asset_id="a-1")
    _consume(db, p1, wo, "3", "2", datetime(2026, 1, 10))   # 6
    _consume(db, p2, wo, "1", "5", datetime(2026, 1, 11))   # 5
    r = svc.cost_dashboard(db, date_from=date(2026, 1, 1), date_to=date(2026, 1, 31))
    assert r["parts_consumption_cost"] == Decimal("11")
    by_part = {row["custom_id"]: row["cost"] for row in r["consumption_by_part"]}
    assert by_part["PRT1"] == Decimal("6") and by_part["PRT2"] == Decimal("5")
    # 降序：cost 高的在前
    assert r["consumption_by_part"][0]["custom_id"] == "PRT1"
    by_asset = {row["asset_id"]: row["cost"] for row in r["consumption_by_asset"]}
    assert by_asset["a-1"] == Decimal("11")


def test_consumption_window_excludes(db: Session):
    p1 = _part(db)
    wo = _wo(db)
    _consume(db, p1, wo, "3", "2", datetime(2025, 12, 31))  # 窗外
    r = svc.cost_dashboard(db, date_from=date(2026, 1, 1), date_to=date(2026, 1, 31))
    assert r["parts_consumption_cost"] == Decimal("0")


def test_po_spend_only_approved_in_window(db: Session):
    p1 = _part(db)
    # APPROVED 在窗 -> 计入
    po1 = PurchaseOrder(custom_id="PO1", vendor_id="v-1",
                        status=PurchaseOrderStatus.APPROVED,
                        resolved_at=datetime(2026, 1, 15), company_id=CO)
    db.add(po1)
    db.flush()
    db.add(PurchaseOrderLine(purchase_order_id=po1.id, part_id=p1.id,
                             quantity=Decimal("2"), unit_cost=Decimal("10"), company_id=CO))
    # SUBMITTED -> 不计
    po2 = PurchaseOrder(custom_id="PO2", vendor_id="v-2",
                        status=PurchaseOrderStatus.SUBMITTED, company_id=CO)
    db.add(po2)
    db.flush()
    db.add(PurchaseOrderLine(purchase_order_id=po2.id, part_id=p1.id,
                             quantity=Decimal("9"), unit_cost=Decimal("9"), company_id=CO))
    db.commit()
    r = svc.cost_dashboard(db, date_from=date(2026, 1, 1), date_to=date(2026, 1, 31))
    assert r["po_spend_approved"] == Decimal("20")
    assert {row["vendor_id"]: row["spend"] for row in r["po_spend_by_vendor"]} == {"v-1": Decimal("20")}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_analytics_cost.py -q`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 写实现**

`backend/app/services/analytics/cost_analytics.py`:
```python
"""成本聚合（只读）：备件消耗成本 + PO 承诺采购额。金额在 Python 用 Decimal 计算。"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.part import Part
from app.models.part_consumption import PartConsumption
from app.models.purchase_order import PurchaseOrder, PurchaseOrderLine
from app.models.purchase_order_status import PurchaseOrderStatus
from app.models.work_order import WorkOrder
from app.services.analytics._common import resolve_window


def cost_dashboard(
    db: Session, *, date_from: date | None = None, date_to: date | None = None,
    asset_id: str | None = None, location_id: str | None = None,
) -> dict:
    start, end_excl, df, dt = resolve_window(date_from, date_to)

    # 备件消耗：join WorkOrder 取 asset_id、join Part 取 custom_id/name
    c_stmt = (
        select(
            PartConsumption.part_id, Part.custom_id, Part.name,
            PartConsumption.quantity, PartConsumption.unit_cost, WorkOrder.asset_id,
        )
        .join(WorkOrder, PartConsumption.work_order_id == WorkOrder.id)
        .join(Part, PartConsumption.part_id == Part.id)
        .where(PartConsumption.consumed_at >= start, PartConsumption.consumed_at < end_excl)
    )
    if asset_id is not None:
        c_stmt = c_stmt.where(WorkOrder.asset_id == asset_id)
    if location_id is not None:
        c_stmt = c_stmt.where(WorkOrder.location_id == location_id)
    rows = db.execute(c_stmt).all()

    total_consumption = Decimal("0")
    by_part: dict[str, dict] = {}
    by_asset: dict[str | None, Decimal] = defaultdict(lambda: Decimal("0"))
    for part_id, custom_id, name, qty, unit_cost, a_id in rows:
        line_cost = (qty * unit_cost)
        total_consumption += line_cost
        slot = by_part.setdefault(
            part_id, {"part_id": part_id, "custom_id": custom_id, "name": name,
                      "qty": Decimal("0"), "cost": Decimal("0")})
        slot["qty"] += qty
        slot["cost"] += line_cost
        by_asset[a_id] += line_cost

    consumption_by_part = sorted(by_part.values(), key=lambda r: r["cost"], reverse=True)
    consumption_by_asset = sorted(
        ({"asset_id": k, "cost": v} for k, v in by_asset.items()),
        key=lambda r: r["cost"], reverse=True)

    # PO 承诺采购额：仅 APPROVED 且 resolved_at 在窗
    p_stmt = (
        select(PurchaseOrder.vendor_id, PurchaseOrderLine.quantity, PurchaseOrderLine.unit_cost)
        .join(PurchaseOrderLine, PurchaseOrderLine.purchase_order_id == PurchaseOrder.id)
        .where(
            PurchaseOrder.is_active.is_(True),
            PurchaseOrder.status == PurchaseOrderStatus.APPROVED,
            PurchaseOrder.resolved_at >= start,
            PurchaseOrder.resolved_at < end_excl,
        )
    )
    po_total = Decimal("0")
    by_vendor: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for vendor_id, qty, unit_cost in db.execute(p_stmt).all():
        line = qty * unit_cost
        po_total += line
        by_vendor[vendor_id] += line
    po_spend_by_vendor = sorted(
        ({"vendor_id": k, "spend": v} for k, v in by_vendor.items()),
        key=lambda r: r["spend"], reverse=True)

    return {
        "date_from": df, "date_to": dt,
        "parts_consumption_cost": total_consumption,
        "consumption_by_part": consumption_by_part,
        "consumption_by_asset": consumption_by_asset,
        "po_spend_approved": po_total,
        "po_spend_by_vendor": po_spend_by_vendor,
    }
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_analytics_cost.py -q`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/services/analytics/cost_analytics.py backend/tests/unit/test_analytics_cost.py
git commit -m "$(printf 'feat(phase-4): add cost analytics aggregation\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 6: 资产可靠性聚合 service（可用率/MTBF/MTTR）

**Files:**
- Create: `backend/app/services/analytics/asset_reliability_analytics.py`
- Test: `backend/tests/unit/test_analytics_asset_reliability.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_analytics_asset_reliability.py`:
```python
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.asset_downtime import AssetDowntime
from app.models.maintenance_asset import Asset
from app.services.analytics import asset_reliability_analytics as svc

CO = "co-1"


def _asset(db, custom_id="AST1", name="pump", location_id=None, category_id=None):
    a = Asset(custom_id=custom_id, name=name, location_id=location_id,
              category_id=category_id, company_id=CO)
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def _down(db, asset, started_at, ended_at=None):
    db.add(AssetDowntime(asset_id=asset.id, started_at=started_at, ended_at=ended_at,
                         company_id=CO))
    db.commit()


def test_no_downtime_full_availability(db: Session):
    _asset(db)
    r = svc.asset_reliability_dashboard(db, date_from=date(2026, 1, 1), date_to=date(2026, 1, 1))
    assert r["window_hours"] == 24.0
    row = r["assets"][0]
    assert row["availability_pct"] == 100.0 and row["downtime_count"] == 0
    assert row["mttr_hours"] is None and row["mtbf_hours"] is None


def test_downtime_availability_mttr_mtbf(db: Session):
    a = _asset(db)
    # 窗口 1/1 00:00 .. 1/2 00:00（24h）。停机 6h。
    _down(db, a, datetime(2026, 1, 1, 0), datetime(2026, 1, 1, 6))
    r = svc.asset_reliability_dashboard(db, date_from=date(2026, 1, 1), date_to=date(2026, 1, 1))
    row = r["assets"][0]
    assert row["total_downtime_hours"] == 6.0
    assert row["availability_pct"] == 75.0          # (24-6)/24
    assert row["mttr_hours"] == 6.0
    assert row["mtbf_hours"] == 18.0                # uptime 18 / 1 次


def test_ongoing_downtime_clipped_to_window_end(db: Session):
    a = _asset(db)
    _down(db, a, datetime(2026, 1, 1, 12), None)    # 进行中 -> 裁到 1/2 00:00 = 12h
    r = svc.asset_reliability_dashboard(db, date_from=date(2026, 1, 1), date_to=date(2026, 1, 1))
    row = r["assets"][0]
    assert row["total_downtime_hours"] == 12.0
    assert row["mttr_hours"] is None                # 进行中区间不计入 MTTR


def test_filter_by_location(db: Session):
    _asset(db, custom_id="A1", location_id="loc-1")
    _asset(db, custom_id="A2", location_id="loc-2")
    r = svc.asset_reliability_dashboard(db, date_from=date(2026, 1, 1), date_to=date(2026, 1, 1),
                                        location_id="loc-1")
    assert {row["custom_id"] for row in r["assets"]} == {"A1"}


def test_fleet_rollup(db: Session):
    a1 = _asset(db, custom_id="A1")
    a2 = _asset(db, custom_id="A2")
    _down(db, a1, datetime(2026, 1, 1, 0), datetime(2026, 1, 1, 6))
    r = svc.asset_reliability_dashboard(db, date_from=date(2026, 1, 1), date_to=date(2026, 1, 1))
    assert r["fleet_total_downtime_hours"] == 6.0
    assert r["fleet_availability_pct"] == 87.5      # (75 + 100)/2
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_analytics_asset_reliability.py -q`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 写实现**

`backend/app/services/analytics/asset_reliability_analytics.py`:
```python
"""资产可靠性聚合（只读）：可用率/MTTR/MTBF。停机区间裁剪 + 时长在 Python 计算。

语义：基于窗内全部停机区间，未区分故障/计划（现停机无故障分类）。
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.asset_downtime import AssetDowntime
from app.models.maintenance_asset import Asset
from app.services.analytics._common import clip_interval, hours_between, resolve_window


def asset_reliability_dashboard(
    db: Session, *, date_from: date | None = None, date_to: date | None = None,
    asset_id: str | None = None, location_id: str | None = None,
    category_id: str | None = None,
) -> dict:
    start, end_excl, df, dt = resolve_window(date_from, date_to)
    window_hours = round(hours_between(start, end_excl), 2)

    a_stmt = select(Asset).where(Asset.is_active.is_(True))
    if asset_id is not None:
        a_stmt = a_stmt.where(Asset.id == asset_id)
    if location_id is not None:
        a_stmt = a_stmt.where(Asset.location_id == location_id)
    if category_id is not None:
        a_stmt = a_stmt.where(Asset.category_id == category_id)
    assets = list(db.execute(a_stmt.order_by(Asset.custom_id)).scalars().all())

    asset_rows = []
    for a in assets:
        downs = db.execute(
            select(AssetDowntime).where(
                AssetDowntime.asset_id == a.id,
                AssetDowntime.started_at < end_excl,
                or_(AssetDowntime.ended_at.is_(None), AssetDowntime.ended_at > start),
            )
        ).scalars().all()
        clipped = [
            clip_interval(d.started_at, d.ended_at, start, end_excl) for d in downs
        ]
        clipped = [c for c in clipped if c is not None]
        total_down = sum((hours_between(lo, hi) for lo, hi in clipped), 0.0)
        count = len(clipped)
        availability = round((window_hours - total_down) / window_hours * 100, 2) \
            if window_hours > 0 else 0.0
        availability = max(0.0, min(100.0, availability))
        # MTTR 仅计已结束区间
        ended_durations = [
            hours_between(*clip_interval(d.started_at, d.ended_at, start, end_excl))
            for d in downs
            if d.ended_at is not None
            and clip_interval(d.started_at, d.ended_at, start, end_excl) is not None
        ]
        mttr = round(sum(ended_durations) / len(ended_durations), 2) if ended_durations else None
        mtbf = round((window_hours - total_down) / count, 2) if count else None
        asset_rows.append({
            "asset_id": a.id, "custom_id": a.custom_id, "name": a.name,
            "availability_pct": availability, "downtime_count": count,
            "total_downtime_hours": round(total_down, 2),
            "mttr_hours": mttr, "mtbf_hours": mtbf,
        })

    fleet_total_down = round(sum(r["total_downtime_hours"] for r in asset_rows), 2)
    fleet_availability = round(
        sum(r["availability_pct"] for r in asset_rows) / len(asset_rows), 2
    ) if asset_rows else None
    mttrs = [r["mttr_hours"] for r in asset_rows if r["mttr_hours"] is not None]
    fleet_mttr = round(sum(mttrs) / len(mttrs), 2) if mttrs else None
    mtbfs = [r["mtbf_hours"] for r in asset_rows if r["mtbf_hours"] is not None]
    fleet_mtbf = round(sum(mtbfs) / len(mtbfs), 2) if mtbfs else None

    return {
        "date_from": df, "date_to": dt, "window_hours": window_hours,
        "assets": asset_rows,
        "fleet_availability_pct": fleet_availability,
        "fleet_total_downtime_hours": fleet_total_down,
        "fleet_mttr_hours": fleet_mttr, "fleet_mtbf_hours": fleet_mtbf,
    }
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_analytics_asset_reliability.py -q`
Expected: PASS（5 passed）

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/services/analytics/asset_reliability_analytics.py backend/tests/unit/test_analytics_asset_reliability.py
git commit -m "$(printf 'feat(phase-4): add asset reliability analytics aggregation\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 7: 库存聚合 service（价值/低库存/消耗 top）

**Files:**
- Create: `backend/app/services/analytics/inventory_analytics.py`
- Test: `backend/tests/unit/test_analytics_inventory.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_analytics_inventory.py`:
```python
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.part import Part
from app.models.part_category import PartCategory
from app.models.part_consumption import PartConsumption
from app.models.work_order import WorkOrder
from app.services.analytics import inventory_analytics as svc

CO = "co-1"


def _part(db, *, custom_id="PRT1", name="x", cost="0", quantity="0", min_quantity="0",
          non_stock=False, category_id=None, is_active=True):
    p = Part(custom_id=custom_id, name=name, cost=Decimal(cost), quantity=Decimal(quantity),
             min_quantity=Decimal(min_quantity), non_stock=non_stock,
             category_id=category_id, is_active=is_active, company_id=CO)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def test_total_value_excludes_non_stock_and_inactive(db: Session):
    _part(db, custom_id="A", cost="10", quantity="5")              # 50
    _part(db, custom_id="B", cost="100", quantity="2", non_stock=True)  # 排除
    _part(db, custom_id="C", cost="9", quantity="9", is_active=False)   # 排除
    r = svc.inventory_dashboard(db)
    assert r["total_inventory_value"] == Decimal("50")


def test_value_by_category(db: Session):
    cat = PartCategory(name="轴承类", company_id=CO)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    _part(db, custom_id="A", cost="10", quantity="2", category_id=cat.id)  # 20
    _part(db, custom_id="B", cost="5", quantity="2")                        # 无分类 20->10
    r = svc.inventory_dashboard(db)
    by_cat = {row["name"]: row["value"] for row in r["inventory_value_by_category"]}
    assert by_cat["轴承类"] == Decimal("20")
    assert by_cat[None] == Decimal("10")


def test_low_stock(db: Session):
    _part(db, custom_id="LOW", quantity="1", min_quantity="5")    # 低
    _part(db, custom_id="OK", quantity="5", min_quantity="5")     # 等于不算低
    _part(db, custom_id="NS", quantity="0", min_quantity="9", non_stock=True)  # non_stock 不算
    r = svc.inventory_dashboard(db)
    assert r["low_stock_count"] == 1
    item = r["low_stock_items"][0]
    assert item["custom_id"] == "LOW" and item["shortfall"] == Decimal("4")


def test_top_consumed_in_window(db: Session):
    p1 = _part(db, custom_id="P1")
    p2 = _part(db, custom_id="P2")
    wo = WorkOrder(custom_id="WO1", title="t", created_at=datetime(2026, 1, 5), company_id=CO)
    db.add(wo)
    db.commit()
    db.refresh(wo)
    db.add(PartConsumption(part_id=p1.id, work_order_id=wo.id, quantity=Decimal("2"),
                           unit_cost=Decimal("1"), consumed_at=datetime(2026, 1, 10), company_id=CO))
    db.add(PartConsumption(part_id=p2.id, work_order_id=wo.id, quantity=Decimal("7"),
                           unit_cost=Decimal("1"), consumed_at=datetime(2026, 1, 10), company_id=CO))
    db.commit()
    r = svc.inventory_dashboard(db, date_from=date(2026, 1, 1), date_to=date(2026, 1, 31))
    assert r["top_consumed_parts"][0]["custom_id"] == "P2"   # 量大在前
    assert r["top_consumed_parts"][0]["qty"] == Decimal("7")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_analytics_inventory.py -q`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 写实现**

`backend/app/services/analytics/inventory_analytics.py`:
```python
"""库存聚合（只读）：库存价值（当前快照）+ 低库存 + 窗内 top 消耗。金额 Python Decimal。"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.part import Part
from app.models.part_category import PartCategory
from app.models.part_consumption import PartConsumption
from app.services.analytics._common import resolve_window


def inventory_dashboard(
    db: Session, *, date_from: date | None = None, date_to: date | None = None,
    category_id: str | None = None,
) -> dict:
    p_stmt = select(Part).where(Part.is_active.is_(True), Part.non_stock.is_(False))
    if category_id is not None:
        p_stmt = p_stmt.where(Part.category_id == category_id)
    parts = list(db.execute(p_stmt.order_by(Part.custom_id)).scalars().all())

    # 分类名映射
    cat_names = dict(db.execute(select(PartCategory.id, PartCategory.name)).all())

    total_value = Decimal("0")
    by_cat_value: dict[str | None, Decimal] = defaultdict(lambda: Decimal("0"))
    low_items = []
    for p in parts:
        value = p.quantity * p.cost
        total_value += value
        by_cat_value[p.category_id] += value
        if p.quantity < p.min_quantity:
            low_items.append({
                "part_id": p.id, "custom_id": p.custom_id, "name": p.name,
                "quantity": p.quantity, "min_quantity": p.min_quantity,
                "shortfall": p.min_quantity - p.quantity,
            })

    inventory_value_by_category = sorted(
        ({"category_id": k, "name": cat_names.get(k), "value": v}
         for k, v in by_cat_value.items()),
        key=lambda r: r["value"], reverse=True)

    # 窗内 top 消耗（按量降序）
    start, end_excl, df, dt = resolve_window(date_from, date_to)
    c_stmt = (
        select(PartConsumption.part_id, Part.custom_id, Part.name, PartConsumption.quantity)
        .join(Part, PartConsumption.part_id == Part.id)
        .where(PartConsumption.consumed_at >= start, PartConsumption.consumed_at < end_excl)
    )
    if category_id is not None:
        c_stmt = c_stmt.where(Part.category_id == category_id)
    consumed: dict[str, dict] = {}
    for part_id, custom_id, name, qty in db.execute(c_stmt).all():
        slot = consumed.setdefault(
            part_id, {"part_id": part_id, "custom_id": custom_id, "name": name,
                      "qty": Decimal("0")})
        slot["qty"] += qty
    top_consumed = sorted(consumed.values(), key=lambda r: r["qty"], reverse=True)

    return {
        "total_inventory_value": total_value,
        "inventory_value_by_category": inventory_value_by_category,
        "low_stock_count": len(low_items),
        "low_stock_items": low_items,
        "top_consumed_parts": top_consumed,
    }
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/unit/test_analytics_inventory.py -q`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/services/analytics/inventory_analytics.py backend/tests/unit/test_analytics_inventory.py
git commit -m "$(printf 'feat(phase-4): add inventory analytics aggregation\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 8: router — 4 个 JSON 仪表盘端点 + main 挂载

**Files:**
- Create: `backend/app/routers/analytics.py`
- Modify: `backend/app/main.py`（import 块 + include_router）
- Test: `backend/tests/test_analytics_api.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_analytics_api.py`:
```python
"""分析 API（Phase 4）：鉴权/RBAC/形状/跨租户。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.models.company import Company
from app.models.work_order import WorkOrder


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post("/api/v1/auth/register", json={
        "company_name": company, "email": email,
        "password": "secret123", "name": "Admin"}).json()["access_token"]


def _technician_token(client, admin_token):
    roles = client.get("/api/v1/roles", headers=_h(admin_token)).json()
    rid = next(r["id"] for r in roles if r["code"] == "technician")
    client.post("/api/v1/users", headers=_h(admin_token), json={
        "email": "tech@acme.com", "password": "secret123", "name": "T", "role_id": rid})
    return client.post("/api/v1/auth/login", json={
        "company_slug": "acme", "email": "tech@acme.com",
        "password": "secret123"}).json()["access_token"]


def _company_id(db, slug):
    return db.execute(select(Company).where(Company.slug == slug)).scalar_one().id


def test_all_four_dashboards_200(client):
    t = _admin(client)
    for path in ("work-orders", "costs", "asset-reliability", "inventory"):
        r = client.get(f"/api/v1/analytics/{path}", headers=_h(t))
        assert r.status_code == 200, (path, r.text)


def test_requires_auth(client):
    assert client.get("/api/v1/analytics/work-orders").status_code == 401


def test_technician_forbidden(client):
    admin = _admin(client)
    tech = _technician_token(client, admin)
    assert client.get("/api/v1/analytics/work-orders", headers=_h(tech)).status_code == 403


def test_work_order_dashboard_counts(client, db):
    t = _admin(client)
    co = _company_id(db, "acme")
    db.add(WorkOrder(custom_id="WO1", title="t", created_at=datetime.utcnow(), company_id=co))
    db.commit()
    body = client.get("/api/v1/analytics/work-orders", headers=_h(t)).json()
    assert body["total"] == 1 and "by_status" in body


def test_tenant_isolation(client, db):
    ta = _admin(client, company="Acme", email="a@acme.com")
    tb = _admin(client, company="Beta", email="b@beta.com")
    co_a = _company_id(db, "acme")
    db.add(WorkOrder(custom_id="WO1", title="t", created_at=datetime.utcnow(), company_id=co_a))
    db.commit()
    assert client.get("/api/v1/analytics/work-orders", headers=_h(ta)).json()["total"] == 1
    assert client.get("/api/v1/analytics/work-orders", headers=_h(tb)).json()["total"] == 0
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_analytics_api.py -q`
Expected: FAIL（404 / 路由不存在）

- [ ] **Step 3: 写 router**

`backend/app/routers/analytics.py`:
```python
"""分析 API（/api/v1/analytics）。只读聚合，全部需 analytics.view。"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import permissions
from app.deps import get_db, require_permission
from app.models.user import User
from app.schemas.analytics import (
    AssetReliabilityAnalytics,
    CostAnalytics,
    InventoryAnalytics,
    WorkOrderAnalytics,
)
from app.services.analytics import (
    asset_reliability_analytics,
    cost_analytics,
    inventory_analytics,
    work_order_analytics,
)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

_VIEW = Depends(require_permission(permissions.ANALYTICS_VIEW))


@router.get("/work-orders", response_model=WorkOrderAnalytics)
def work_order_dashboard(
    date_from: date | None = None, date_to: date | None = None,
    asset_id: str | None = None, location_id: str | None = None,
    db: Session = Depends(get_db), current_user: User = _VIEW,
):
    return work_order_analytics.work_order_dashboard(
        db, date_from=date_from, date_to=date_to,
        asset_id=asset_id, location_id=location_id)


@router.get("/costs", response_model=CostAnalytics)
def cost_dashboard(
    date_from: date | None = None, date_to: date | None = None,
    asset_id: str | None = None, location_id: str | None = None,
    db: Session = Depends(get_db), current_user: User = _VIEW,
):
    return cost_analytics.cost_dashboard(
        db, date_from=date_from, date_to=date_to,
        asset_id=asset_id, location_id=location_id)


@router.get("/asset-reliability", response_model=AssetReliabilityAnalytics)
def asset_reliability_dashboard(
    date_from: date | None = None, date_to: date | None = None,
    asset_id: str | None = None, location_id: str | None = None,
    category_id: str | None = None,
    db: Session = Depends(get_db), current_user: User = _VIEW,
):
    return asset_reliability_analytics.asset_reliability_dashboard(
        db, date_from=date_from, date_to=date_to,
        asset_id=asset_id, location_id=location_id, category_id=category_id)


@router.get("/inventory", response_model=InventoryAnalytics)
def inventory_dashboard(
    date_from: date | None = None, date_to: date | None = None,
    category_id: str | None = None,
    db: Session = Depends(get_db), current_user: User = _VIEW,
):
    return inventory_analytics.inventory_dashboard(
        db, date_from=date_from, date_to=date_to, category_id=category_id)
```

- [ ] **Step 4: 挂载到 `app/main.py`**

先 Read 文件。在 `from app.routers import (...)` 块内 `purchase_orders,` 行之后插入一行：
```python
    analytics,
```
在 `app.include_router(purchase_orders.router)` 行之后插入：
```python
app.include_router(analytics.router)
```

- [ ] **Step 5: 跑测试 + 导入冒烟**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_analytics_api.py -q && python -c "import app.main"`
Expected: PASS（5 passed）+ 无导入错误

- [ ] **Step 6: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/routers/analytics.py backend/app/main.py backend/tests/test_analytics_api.py
git commit -m "$(printf 'feat(phase-4): add analytics JSON dashboard endpoints + mount\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 9: CSV 导出端点（每盘主分组明细）

**Files:**
- Modify: `backend/app/routers/analytics.py`（追加 CSV helper + 导出端点）
- Test: `backend/tests/test_analytics_export.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_analytics_export.py`:
```python
"""分析 CSV 导出（Phase 4）。"""
from __future__ import annotations


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post("/api/v1/auth/register", json={
        "company_name": company, "email": email,
        "password": "secret123", "name": "Admin"}).json()["access_token"]


def test_export_csv_content_type_and_header(client):
    t = _admin(client)
    r = client.get("/api/v1/analytics/work-orders/export", headers=_h(t))
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    first_line = r.text.splitlines()[0]
    assert first_line == "status,count,pct"


def test_export_rows_match_breakdown(client):
    t = _admin(client)
    r = client.get("/api/v1/analytics/work-orders/export", headers=_h(t))
    # 工单盘按 5 个状态各一行 + 表头
    lines = [ln for ln in r.text.splitlines() if ln.strip()]
    assert len(lines) == 1 + 5


def test_export_all_dashboards_csv(client):
    t = _admin(client)
    expected_headers = {
        "work-orders": "status,count,pct",
        "costs": "part_id,custom_id,name,qty,cost",
        "asset-reliability": "asset_id,custom_id,name,availability_pct,downtime_count,total_downtime_hours,mttr_hours,mtbf_hours",
        "inventory": "custom_id,name,category,quantity,min_quantity,cost,value,is_low_stock",
    }
    for dash, header in expected_headers.items():
        r = client.get(f"/api/v1/analytics/{dash}/export", headers=_h(t))
        assert r.status_code == 200, (dash, r.text)
        assert r.text.splitlines()[0] == header


def test_export_invalid_dashboard_404(client):
    t = _admin(client)
    assert client.get("/api/v1/analytics/nope/export", headers=_h(t)).status_code == 404


def test_export_requires_permission(client):
    assert client.get("/api/v1/analytics/work-orders/export").status_code == 401
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_analytics_export.py -q`
Expected: FAIL（导出端点不存在 → 404/405）

- [ ] **Step 3: 追加 CSV 导出到 `app/routers/analytics.py`**

在文件顶部 import 区追加：
```python
import csv
import io

from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse

from app.models.part import Part
```
（注：`Part` 用于库存导出取分类名映射；若已存在同名 import 勿重复。）

在文件末尾追加 CSV helper 与导出端点：
```python
def _stream_csv(header: list[str], rows: list[list]) -> StreamingResponse:
    def gen():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(header)
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)
        for row in rows:
            writer.writerow(row)
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

    return StreamingResponse(
        gen(), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=analytics.csv"},
    )


def _work_orders_csv(data: dict) -> tuple[list[str], list[list]]:
    total = data["total"]
    rows = [
        [status_name, count, round(count / total, 4) if total else 0.0]
        for status_name, count in data["by_status"].items()
    ]
    return ["status", "count", "pct"], rows


def _costs_csv(data: dict) -> tuple[list[str], list[list]]:
    rows = [
        [r["part_id"], r["custom_id"], r["name"], r["qty"], r["cost"]]
        for r in data["consumption_by_part"]
    ]
    return ["part_id", "custom_id", "name", "qty", "cost"], rows


def _asset_reliability_csv(data: dict) -> tuple[list[str], list[list]]:
    rows = [
        [r["asset_id"], r["custom_id"], r["name"], r["availability_pct"],
         r["downtime_count"], r["total_downtime_hours"], r["mttr_hours"], r["mtbf_hours"]]
        for r in data["assets"]
    ]
    return (["asset_id", "custom_id", "name", "availability_pct", "downtime_count",
             "total_downtime_hours", "mttr_hours", "mtbf_hours"], rows)


def _inventory_csv(db: Session, data: dict) -> tuple[list[str], list[list]]:
    cat_names = dict(db.execute(select(PartCategory.id, PartCategory.name)).all())
    low_ids = {r["part_id"] for r in data["low_stock_items"]}
    parts = list(db.execute(
        select(Part).where(Part.is_active.is_(True), Part.non_stock.is_(False))
        .order_by(Part.custom_id)).scalars().all())
    rows = [
        [p.custom_id, p.name, cat_names.get(p.category_id), p.quantity, p.min_quantity,
         p.cost, p.quantity * p.cost, p.id in low_ids]
        for p in parts
    ]
    return (["custom_id", "name", "category", "quantity", "min_quantity", "cost",
             "value", "is_low_stock"], rows)


@router.get("/{dashboard}/export")
def export_dashboard_csv(
    dashboard: str,
    date_from: date | None = None, date_to: date | None = None,
    asset_id: str | None = None, location_id: str | None = None,
    category_id: str | None = None,
    db: Session = Depends(get_db), current_user: User = _VIEW,
):
    if dashboard == "work-orders":
        data = work_order_analytics.work_order_dashboard(
            db, date_from=date_from, date_to=date_to,
            asset_id=asset_id, location_id=location_id)
        header, rows = _work_orders_csv(data)
    elif dashboard == "costs":
        data = cost_analytics.cost_dashboard(
            db, date_from=date_from, date_to=date_to,
            asset_id=asset_id, location_id=location_id)
        header, rows = _costs_csv(data)
    elif dashboard == "asset-reliability":
        data = asset_reliability_analytics.asset_reliability_dashboard(
            db, date_from=date_from, date_to=date_to,
            asset_id=asset_id, location_id=location_id, category_id=category_id)
        header, rows = _asset_reliability_csv(data)
    elif dashboard == "inventory":
        data = inventory_analytics.inventory_dashboard(
            db, date_from=date_from, date_to=date_to, category_id=category_id)
        header, rows = _inventory_csv(db, data)
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ANALYTICS_DASHBOARD_NOT_FOUND", "message": "未知分析面板"})
    return _stream_csv(header, rows)
```
还需在顶部 import 区补 `from app.models.part_category import PartCategory` 与 `from sqlalchemy import select`（若 Task 8 未引入则在此引入；若 router 顶部已无 `select` 则加）。先 Read 文件确认现有 import，仅补缺失项，勿重复。

> 注：`/{dashboard}/export` 与 Task 8 的 4 个字面路径不冲突（路径段不同）；FastAPI 会优先匹配字面 `/work-orders` 等。导出端点同样受 `_VIEW` 守护。

- [ ] **Step 4: 跑测试确认通过 + 导入冒烟**

Run: `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_analytics_export.py tests/test_analytics_api.py -q && python -c "import app.main"`
Expected: PASS（导出 5 + API 5）+ 无导入错误

- [ ] **Step 5: 提交**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git add backend/app/routers/analytics.py backend/tests/test_analytics_export.py
git commit -m "$(printf 'feat(phase-4): add analytics CSV export endpoints\n\nCo-Authored-By: Claude Opus 4.5 (1M context) <noreply@anthropic.com>')"
```

---

## Task 10: 全量回归 + ruff + 收尾

**Files:** 无新增（仅验证）

- [ ] **Step 1: 清缓存跑全量测试，tee 到唯一文件**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate
find . -name __pycache__ -type d -exec rm -rf {} + ; rm -rf .pytest_cache
PYTHONDONTWRITEBYTECODE=1 pytest -q 2>&1 | tee /tmp/p4_fullrun_$(date +%s).txt | tail -5
```
Expected: 末行 `N passed`（N ≥ 945 + 新增；0 failed）。Read tee 文件确认真实摘要行（防陈旧回放）。

- [ ] **Step 2: ruff 静态检查（仅本期文件）**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate
ruff check app/services/analytics app/routers/analytics.py app/schemas/analytics.py app/permissions.py
```
Expected: `All checks passed!`（若报未用 import 等，按提示在对应文件用 Edit 精确修正后重跑）。

- [ ] **Step 3: alembic 单 head + Atlas 扫描 + 工作树**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/backend" && source .venv/bin/activate && alembic heads
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && grep -ric atlas backend/app/services/analytics backend/app/routers/analytics.py backend/app/schemas/analytics.py
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP" && git log --oneline -9
```
Expected: `alembic heads` 仅 `phase3c_purchase_order (head)`（本期零新表零迁移）；Atlas 计数全 0；提交链含 Task 1–9 各一次。

> 注：`git status --porcelain` 可能显示其他会话遗留的游离改动（非本期）；只需确认**本期文件**均已提交、无遗漏，勿提交非本期改动。

---

## 完成标准（Definition of Done）

- 全量 pytest 0 failed（含新增 4 盘单测 + common/schema 单测 + API 测 + 导出测 + 权限契约测）。
- `/api/v1/analytics` 4 个 JSON 仪表盘 + 4 个 CSV 导出端点工作，全部受 `analytics.view` 守护；technician 403、viewer/admin/super_admin 可见。
- 4 盘 KPI 口径与设计 spec 第 4 节一致；时间窗（默认 90 天）+ 维度过滤生效；跨租户隔离正确（聚合只见本租户）。
- CSV 流式 `text/csv`、表头正确、行数与分组一致；非法 `{dashboard}` 导出 404。
- ruff 干净；clean-room 无 "Atlas"。
- alembic 仍单 head `phase3c_purchase_order`（零新表零迁移）。
