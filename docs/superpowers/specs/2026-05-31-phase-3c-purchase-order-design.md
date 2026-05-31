# Phase 3C 采购单（Purchase Order）设计 spec

> Phase 3（库存与采购）拆为三个独立周期（3A 备件/库存/消耗/套件 · 3B 供应商/客户/成本分类 · **3C 采购单 PO + 审批→入库**），各自走完整 spec→plan→implement。本文是 **3C**，承接 [3A 备件/库存](2026-05-31-phase-3a-parts-inventory-design.md) 与 [3B 供应商/客户](2026-05-31-phase-3b-vendor-customer-design.md)，依据 [总体路线图](2026-05-30-smart-cmms-master-roadmap-design.md) 与 [功能对照矩阵](2026-05-30-feature-parity-matrix.md) IN3。

- **日期**: 2026-05-31
- **状态**: 已批准（brainstorming 协作产出）

## 1. 目标与范围

实现采购闭环：**采购单 PO → 提交 → 审批（=整单入库回写 `Part.quantity`）**。PO 头引用 3B 的 Vendor，PO 行引用 3A 的 Part（+ 数量 + 单价）。审批通过即整单收货，逐行把数量加回各 `Part.quantity`（non_stock 备件不增数量但行照常记录）。纯事务单据，复用既有 Vendor/Part，零侵入 3A/3B 代码。是 Phase 4（采购成本分析）与库存补货链路的基础。

### 纳入范围
- `PurchaseOrder` 采购单头：custom_id（`PO%06d`）+ vendor_id（**必填**）+ status + notes + 审批结果字段。M:N/1:N → PO 行。
- `PurchaseOrderLine` 采购行：part_id + quantity + unit_cost（采购单价快照，独立于 `Part.cost`）。
- `PurchaseOrderActivity` 活动时间线：append-only，镜像 `tb_request_activity`。
- 状态机 DRAFT→SUBMITTED→APPROVED|REJECTED（+ DRAFT/SUBMITTED 可 CANCELED），approve 原子入库回写。
- 行编辑：create 携带 lines[]；仅 DRAFT 可 update 头与 lines（全量替换）；submit 需 ≥1 行。
- `/mini` 下拉端点。
- RBAC：`purchase_order.{view,create,edit,delete,approve}`，approve 仅 admin/super_admin。

### 不纳入范围（明确延后）
- **部分/逐行收货**（received_qty 累加、fully/partially_received 态）：本期审批通过=整单一次性入库，无逐行收货状态。
- **加权平均 / 最近进价回写 `Part.cost`**：本期入库只增 `Part.quantity`，不动 `Part.cost`；PO 行的 unit_cost 仅作采购价快照。
- **采购退货 / 冲销 / 撤销已审批 PO**：APPROVED 为终态，不支持反向回退库存。
- **多币种 / 税费 / 折扣 / 运费**：PO 总额仅为 Σ 行 quantity×unit_cost。
- **附件 / 自定义字段 / 期望到货日**：Phase 6 商业化。
- **Part.cost / Vendor.rate 的消费端分析**（采购成本汇总、供应商绩效）→ Phase 4 分析期。

### 沿用既有不变约束
clean-room、零 GPL 风险（输出不出现 "Atlas" 字样、不抄源码/DDL/文案）、多租户隔离（中间件 + ORM 事件，读写在请求内无需 bypass）、`tb_` 前缀、UUID 字符串主键、软删 `is_active`/`deleted_at`、money/qty 用 `Numeric(18,4)` 裸金额、custom_id 经 sequence_service（每租户 scope 计数）。

## 2. 数据模型

共 **3 张新表**（均 `tb_` 前缀、UUID 主键、TenantMixin 盖租户章）。

### ① `tb_purchase_order` 采购单头（+ SoftDeleteMixin）
| 字段 | 类型 | 说明 |
|---|---|---|
| custom_id | String(20), nullable=False | `PO%06d`，sequence_service scope=`purchase_order` |
| vendor_id | String(36) FK tb_vendor ondelete=**RESTRICT**, nullable=False, index | **必填**，保护被引用供应商 |
| status | SAEnum(PurchaseOrderStatus), nullable=False, default DRAFT | 见 §3 |
| notes | Text, default "", server_default "" | 采购备注 |
| resolution_note | Text, default "", server_default "" | 审批/拒绝/取消理由 |
| resolved_by_user_id | String(36), nullable | 处理人（approve/reject/cancel 操作者） |
| resolved_at | DATETIME6, nullable | 处理时间 |

> `total_cost`（= Σ 行 quantity×unit_cost）**不落库**，在 `PurchaseOrderRead` 计算（镜像 3A `PartConsumptionRead.total_cost`）。

### ② `tb_purchase_order_line` 采购行（仅 TimestampMixin + TenantMixin，无软删）
| 字段 | 类型 | 说明 |
|---|---|---|
| purchase_order_id | String(36) FK tb_purchase_order ondelete=**CASCADE**, index | 行属于 PO |
| part_id | String(36) FK tb_part ondelete=**RESTRICT**, index | 引用备件（镜像 part_consumption 的 part_id RESTRICT） |
| quantity | Numeric(18,4), nullable=False | 采购数量 |
| unit_cost | Numeric(18,4), nullable=False | 采购单价快照（独立于 Part.cost） |

> 无唯一约束：同一 PO 允许同一 part_id 出现多行（不同批次/单价）。行无 custom_id、无软删（PO 软删即整单不可见；DRAFT 编辑走全量 delete+re-add）。

### ③ `tb_purchase_order_activity` 活动时间线（append-only，无软删；镜像 `tb_request_activity`）
| 字段 | 类型 | 说明 |
|---|---|---|
| purchase_order_id | String(36) FK tb_purchase_order ondelete=CASCADE, index | |
| activity_type | String | `STATUS_CHANGE` / `RECEIVED` |
| actor_user_id | String(36), nullable | |
| from_status | String, nullable | |
| to_status | String, nullable | |
| comment | Text, default "", server_default "" | |

（字段类型与既有 `RequestActivity` 逐行同构，沿用其列定义惯例。）

## 3. 状态机（`app/models/purchase_order_status.py`，镜像 `request_status.py`）

```
DRAFT ──submit──▶ SUBMITTED ──approve──▶ APPROVED(=已入库)   [终态]
  │                   │
  │                   └──reject──▶ REJECTED                   [终态]
  └──cancel──┐  SUBMITTED ──cancel──┐
             └──────────────────────┴──▶ CANCELED            [终态]
```

- `class PurchaseOrderStatus(str, enum.Enum)`：`DRAFT/SUBMITTED/APPROVED/REJECTED/CANCELED`。
- `can_transition(src, dst) -> bool`，允许集：DRAFT→{SUBMITTED, CANCELED}；SUBMITTED→{APPROVED, REJECTED, CANCELED}；终态（APPROVED/REJECTED/CANCELED）无出边。非法转移 → 400 `PURCHASE_ORDER_BAD_TRANSITION`。
- **approve 原子动作**（单次 commit）：①`can_transition(status, APPROVED)` 否则 400；②逐行 `if not part.non_stock: part.quantity = part.quantity + line.quantity`（non_stock 跳过、不报错、行照常存在）；③status=APPROVED + resolution_note + resolved_by_user_id + resolved_at=utcnow；④写 `STATUS_CHANGE`(SUBMITTED→APPROVED) + `RECEIVED` 两条活动。终态守卫保证库存**恰好回写一次**（重复 approve 被 can_transition 拦截）。
- approve 取各行 part 走 `db.get(Part, line.part_id)`；若行引用的 part 已软删/缺失，approve 跳过其库存回写（不报错，保持入库幂等与健壮）——本期不强校验行 part 存活（沿用 3A category_id 既有宽松模式，不夹带跨模块加固）。

## 4. 行编辑规则

- create 携带 `lines[]`（允许 ≥0 行，便于先建草稿再补行）。
- **仅 DRAFT** 可 update：头标量字段 setattr；`lines` 非 None 时全量替换（先 `delete where purchase_order_id==po.id` 再 re-add，镜像 3A/3B 关联替换）。非 DRAFT update → 400 `PURCHASE_ORDER_NOT_DRAFT`。
- **submit 守卫**：PO 行数 ≥1，否则 400 `PURCHASE_ORDER_EMPTY`。
- delete：软删（is_active=False + deleted_at），任意状态可删（软删仅隐藏，不回退库存）。

## 5. Pydantic Schema（单文件 `app/schemas/purchase_order.py`）

- `POLineCreate`：part_id + quantity(Decimal) + unit_cost(Decimal)。
- `POLineRead`（from_attributes）：id + part_id + quantity + unit_cost + line_total（= quantity×unit_cost，computed）。
- `PurchaseOrderCreate`：vendor_id（**必填**，min_length=1）+ notes(default "") + lines: list[POLineCreate]（default []）。
- `PurchaseOrderUpdate`：vendor_id/notes Optional + lines: list[POLineCreate] | None。
- `PurchaseOrderRead`（from_attributes）：id + custom_id + vendor_id + status + notes + resolution_note + resolved_by_user_id + resolved_at + lines: list[POLineRead] + total_cost（= Σ line_total，由 router 填充/计算）。
- `PurchaseOrderMini`（from_attributes）：id + custom_id + vendor_id + status。
- `POResolve`：note(default "")（approve/reject/cancel 共用请求体）。

## 6. Service 层（`app/services/purchase_order_service.py`，镜像 request_service + part_consumption_service）

- `create_purchase_order(db, payload, company_id, actor_user_id) -> PurchaseOrder`：`sequence_service.next_value(db, "purchase_order", company_id)` + `format_custom_id("PO", seq)`；flush 后 `_set_lines`；单 commit。
- `list_purchase_orders(db, *, status=None, vendor_id=None) -> list[PurchaseOrder]`：`is_active` 真；过滤 status/vendor_id；`order_by(custom_id)`。
- `get_purchase_order(db, po_id) -> PurchaseOrder | None`：软删不可见。
- `update_purchase_order(db, po, payload, ...)`：`_assert_draft`（非 DRAFT → 400 `PURCHASE_ORDER_NOT_DRAFT`）；头 setattr；lines 非 None 则全量替换。
- `delete_purchase_order(db, po)`：软删。
- `submit_purchase_order(db, po, ...)`：行数 0 → 400 `PURCHASE_ORDER_EMPTY`；`_resolve`-风格转 SUBMITTED + STATUS_CHANGE 活动。
- `approve_purchase_order(db, po, note, company_id, actor_user_id)`：§3 原子入库。
- `reject_purchase_order` / `cancel_purchase_order`：转 REJECTED/CANCELED + STATUS_CHANGE 活动（沿用 `_resolve` 守卫）。
- `lines(db, po_id) -> list[PurchaseOrderLine]`（order_by id 确定序）。
- `list_activities(db, po_id)`（order_by created_at, id）。
- `_log(...)`：写 `PurchaseOrderActivity`（镜像 request_service._log）。

## 7. API / 路由（`app/routers/purchase_orders.py`，prefix `/api/v1/purchase-orders`，tag purchase-orders）

- `GET ""`（`?status=`、`?vendor_id=`）→ list[PurchaseOrderRead]，需 `purchase_order.view`。
- `POST ""` → 201 PurchaseOrderRead，需 `purchase_order.create`。
- `GET "/mini"`（**必须注册在 `/{po_id}` 之前**）→ list[PurchaseOrderMini]，需 `purchase_order.view`。
- `GET/PATCH/DELETE "/{po_id}"` → Read / Read / 204，需 view/edit/delete。
- `POST "/{po_id}/submit"` → Read，需 `purchase_order.edit`。
- `POST "/{po_id}/approve"` → Read，需 `purchase_order.approve`。
- `POST "/{po_id}/reject"` → Read，需 `purchase_order.approve`。
- `POST "/{po_id}/cancel"` → Read，需 `purchase_order.edit`。
- `GET "/{po_id}/activities"` → list（活动时间线），需 `purchase_order.view`。
- PurchaseOrderRead 经 `_read(db, po)` 填充 lines + total_cost。
- **跨租户**：每个 `_ensure` 校验 `po.company_id == current_user.company_id`，否则 404 `PURCHASE_ORDER_NOT_FOUND`。
- vendor_id / part_id **不强校验跨租户归属**：沿用 3B 既有模式（跨租户 id 因 ORM 租户作用域在读取时自然不解析，无害）；不夹带跨模块加固决策。

## 8. RBAC（`app/permissions.py` 精确 Edit 插入）

- 新权限码常量：`PURCHASE_ORDER_VIEW/CREATE/EDIT/DELETE/APPROVE`。
- 分组列表：`_PURCHASE_ORDER`。
- `ALL_PERMISSIONS` 末尾追加 `+ _PURCHASE_ORDER`（不丢任何既有组）。
- 角色默认：
  - admin / super_admin：自动全含（含 approve）。
  - **approve 仅 admin/super_admin**（镜像 request.approve：technician/viewer/requester 均无 approve）。
  - **technician**：追加 `PURCHASE_ORDER_VIEW`（只读、不可创建/审批，呼应 3B technician 只读授予）。
  - viewer：自动经 `.endswith(".view")` 含 purchase_order.view。
  - requester：不变（仅 request.view/create）。

## 9. 迁移

单文件 `backend/alembic/versions/20260531_0009_phase3c_purchase_order.py`，`revision = "phase3c_purchase_order"`，`down_revision = "phase3b_vendor"`。hand-authored 双方言（MySQL prod + SQLite test），新表 `create_table`，复用 `_ts()/_soft()/_company_fk()` helper。建 3 表（tb_purchase_order、tb_purchase_order_line、tb_purchase_order_activity）含全部索引（company_id + 各 FK 列）。`upgrade` ↔ `downgrade` 对称（downgrade 先 drop 子表 line/activity 再 drop 父表 purchase_order，索引先于表 drop）。迁移后 `alembic heads` 仅 `phase3c_purchase_order (head)`。

## 10. 测试策略（TDD，逐 task 红→绿→提交）

- 模型：行写入 + 关联 + FK/状态枚举默认 + `__all__` 导出注册。
- 状态机：`can_transition` 合法/非法矩阵。
- 迁移：revision 链 + SQLite upgrade/downgrade 往返（断言 3 表建/删）。
- RBAC 契约：新码注册 + admin/super_admin 全含 + technician 仅 view（无 create/edit/delete/approve）+ viewer 含 view + requester 不变 + approve 仅 admin/super_admin + 既有契约不破。
- schema：必填 vendor_id / 默认 / Optional + lines 默认空 + line_total/total_cost 计算。
- service：CRUD + custom_id 生成 + lines 全量替换（draft-only）+ submit 空单守卫 + approve 入库回写（普通增、non_stock 不增、库存恰回写一次、Part.cost 不变）+ reject/cancel + 非法转移守卫 + 软删不可见。
- router API：CRUD + `/mini` 路由顺序 + submit/approve/reject/cancel/activities + 跨租户 404 + technician 只读 403 + 非 admin approve 403。

预计 ~13–14 个 TDD task。

## 11. 文件清单

**新增：** `app/models/purchase_order.py`(PurchaseOrder + PurchaseOrderLine + PurchaseOrderActivity)、`app/models/purchase_order_status.py`(枚举 + can_transition)；`app/schemas/purchase_order.py`；`app/services/purchase_order_service.py`；`app/routers/purchase_orders.py`；迁移 `alembic/versions/20260531_0009_phase3c_purchase_order.py`。

**修改（共享文件，精确 Edit）：** `app/permissions.py`、`app/models/__init__.py`、`app/main.py`。

## 12. 完成标准（Definition of Done）

- 全量 pytest 0 failed（基线 900 + 本期新增）。
- 3 张表经迁移可 upgrade/downgrade；`alembic heads` 单 head `phase3c_purchase_order`。
- `/purchase-orders` 全套端点工作；状态机 DRAFT→SUBMITTED→APPROVED|REJECTED|CANCELED 守卫正确；approve 整单入库回写 `Part.quantity`（普通增、non_stock 不增、恰回写一次、Part.cost 不变）；submit 空单 400；非 DRAFT 编辑 400；`/mini`；technician 只读、非 admin 不能 approve；跨租户隔离 404。
- clean-room（无 "Atlas" 字样）。
- `git status --porcelain` 干净。
