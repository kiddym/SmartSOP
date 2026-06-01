# Smart CMMS 功能对标矩阵（Feature Parity Matrix）

- **日期**: 2026-05-30
- **用途**: "完整复刻 Atlas 功能"的**全局对账清单**——一行一个功能点,逐条勾销,保证不漏。
- **配套**: [总体路线图](./2026-05-30-smart-cmms-master-roadmap-design.md) · [Atlas 盘点](./2026-05-30-atlas-cmms-inventory-and-dependencies.md)
- **维护方式**: 每完成一个功能点,把状态由 ☐ 改为 ☑;细颗粒度的实现规则在各阶段的 PRD/spec 中展开,本表只做"是否覆盖"的对账。

**状态图例**：☐ 未开始 · ◐ 进行中 · ☑ 已完成 · ⊘ 不复刻 · ✎ 改造(以自有方案替代)

---

## P. 平台 Platform（Phase 0；商业层入 Phase 6）

### P1. 认证 Authentication
| 状态 | 功能点 | 阶段 | 备注/差异 |
|:--:|---|:--:|---|
| ☐ | 注册（新建组织：自动建 Company+Subscription+默认角色，赋 Administrator） | 0 | |
| ☐ | 注册（受邀加入已有组织，校验 UserInvitation） | 0 | |
| ☐ | 登录（邮箱+密码，签发 JWT） | 0 | |
| ☐ | 邮箱激活 / 账号启用 | 0 | |
| ☐ | 找回/重置密码（邮件令牌 VerificationToken） | 0 | |
| ☐ | 修改密码（校验旧密码） | 0 | |
| ☐ | Token 刷新 | 0 | |
| ☐ | SSO / OAuth2（Google/GitHub/Microsoft） | 6 | ✎ license 门控；自有授权方案 |
| ☐ | 超级账号多组织切换（SuperAccountRelation, switch-account） | 后期 | 低优先 |

### P2. 多租户 Multi-tenancy
| 状态 | 功能点 | 阶段 | 备注 |
|:--:|---|:--:|---|
| ☐ | 租户根 Company + 行级 `company_id` 隔离 | 0 | ✎ 用 TenantMixin + DI 上下文 |
| ☐ | 写入自动加租户作用域（≈@PrePersist） | 0 | |
| ☐ | 读取跨租户校验（≈@PostLoad 403） | 0 | |
| ☐ | 列表/搜索查询统一加 company 过滤 | 0 | |
| ☐ | 请求体引用的跨租户对象校验（≈TenantAspect） | 0 | |
| ☐ | 平台级 SUPER_ADMIN 跨租户 | 0 | |

### P3. RBAC / 用户 / 团队
| 状态 | 功能点 | 阶段 | 备注 |
|:--:|---|:--:|---|
| ☐ | Role（每租户，5 权限集 create/view/viewOther/editOther/deleteOther） | 0 | |
| ☐ | 15 个 PermissionEntity 权限域 | 0 | |
| ☐ | 6 个内置默认角色（ADMIN/LIMITED_ADMIN/TECHNICIAN/LIMITED_TECHNICIAN/VIEW_ONLY/REQUESTER） | 0 | |
| ☐ | 自定义角色 CRUD | 0 | 套餐门控 ROLE（Phase 6） |
| ☐ | 方法级权限判定范式（owner=createdBy） | 0 | |
| ☐ | 用户 CRUD / 搜索 / mini 下拉 | 0 | |
| ☐ | 用户邀请（UserInvitation + 邮件） | 0 | |
| ☐ | 改用户角色 / 启用 / 停用 | 0 | |
| ☐ | 团队 Team CRUD（M:N 用户/资产/位置） | 0 | |
| ☐ | 用户个人资料 / 公司资料页 | 0 | |

### P4. 通知 Notifications
| 状态 | 功能点 | 阶段 | 备注 |
|:--:|---|:--:|---|
| ☐ | 站内通知（9 种 NotificationType，seen/read-all） | 0(基础)/5 | |
| ☐ | 实时推送（WebSocket/STOMP） | 5 | |
| ☐ | 邮件通知（按 UserSettings 开关） | 5 | |
| ☐ | 移动端推送（Expo PushNotificationToken） | 7 | |

### P5. 文件 Files
| 状态 | 功能点 | 阶段 | 备注 |
|:--:|---|:--:|---|
| ☐ | 文件上传 / 搜索 / 重命名 / 删除（FileType, hidden） | 0(基础)/5 | SmartSOP 已有 Attachment,需加租户+存储抽象 |
| ☐ | 存储抽象（本地 / S3 兼容） | 5 | ✎ 替代 GCP/MinIO |
| ☐ | 文件挂接到 资产/工单/请求/位置/备件 | 各模块 | |

### P6. 设置 / 配置
| 状态 | 功能点 | 阶段 | 备注 |
|:--:|---|:--:|---|
| ☐ | CompanySettings / GeneralPreferences（语言/日期/币种/时区/自动指派等开关） | 0/6 | |
| ☐ | UiConfiguration（模块可见性开关） | 6 | |
| ☐ | UserSettings（各实体邮件通知开关） | 5 | |
| ☐ | 工单表单字段配置 FieldConfiguration（OPTIONAL/REQUIRED/HIDDEN） | 6 | |
| ☐ | 自定义字段框架（逐实体） | 6 | ✎ 复用 SmartSOP CustomFieldDef（强于 Atlas 仅 Vendor） |
| ☐ | 每公司自增序列 customId（CustomSequence） | 1 | |
| ☐ | 币种 Currency（全局，SUPER_ADMIN 维护） | 0/6 | |

### P7. 商业化（计费/订阅）
| 状态 | 功能点 | 阶段 | 备注 |
|:--:|---|:--:|---|
| ☐ | SubscriptionPlan（16 PlanFeatures，4 档套餐 FREE/STARTER/PRO/BUSINESS） | 6 | |
| ☐ | Subscription（座席 usersCount，试用，月/年） | 6 | |
| ☐ | 功能门控（按套餐 features 判定） | 6 | |
| ☐ | 座席上限校验（邀请/启用/改角色） | 6 | |
| ☐ | 套餐升降级 / 变更请求 SubscriptionChangeRequest | 6 | |
| ☐ | 第三方计费 webhook | 6 | ✎ Stripe 替代 FastSpring |
| ☐ | 自托管授权 license | 6 | ✎ 自有方案替代 Keygen |

---

## WO. 工单与执行 Work Orders（Phase 1；请求/PM/触发器 Phase 2）

### WO1. 工单核心
| 状态 | 功能点 | 阶段 | 备注 |
|:--:|---|:--:|---|
| ☐ | 工单 CRUD（title/description/priority/dueDate/estimatedDuration/estimatedStartDate） | 1 | |
| ☐ | 工单分类 WorkOrderCategory | 1 | |
| ☐ | 状态机 OPEN/IN_PROGRESS/ON_HOLD/COMPLETE + 副作用 | 1 | |
| ☐ | 优先级 NONE/LOW/MEDIUM/HIGH | 1 | |
| ☐ | 指派：primaryUser / team / assignedTo(多) / customers | 1 | |
| ☐ | 绑定资产 / 位置 | 1 | |
| ☐ | 完成记录 completedBy/completedOn + 合规 isCompliant | 1 | |
| ☐ | 首次响应时间 firstTimeToReact（→ MTTA） | 1 | |
| ☐ | 完成签名（File signature） | 1 | 套餐门控 SIGNATURE（P6） |
| ☐ | 反馈 feedback | 1 | |
| ☐ | 归档 archived | 1 | |
| ☐ | 工单附件 add/remove files | 1 | |
| ☐ | 工单看板（按状态）+ 列表视图 | 1 | |
| ☐ | 工单日历视图（events） | 1 | |
| ☐ | 按资产 / 位置 / 备件 查工单 | 1 | |
| ☐ | 紧急工单 urgent | 1 | |
| ☐ | 工单 PDF 报告 | 1 | ✎ 复用 SmartSOP ReportLab |
| ☐ | 工单可编辑性 canBeEditedBy（权限/创建者/被指派） | 1 | |
| ☐ | 工单关联 Relation（DUPLICATE/RELATED/SPLIT/BLOCKS） | 1/后期 | |
| ☐ | 工单历史 WorkOrderHistory（人读事件流） | 1 | |
| ☐ | 工单字段级版本历史（≈Envers） | 后期 | 复用 SmartSOP 审计 |

### WO2. 执行程序（★ SOP 替代 Atlas Task/TaskBase —— 需求 #1 核心）
| 状态 | 功能点 | 阶段 | 备注 |
|:--:|---|:--:|---|
| ⊘ | Atlas 扁平 Task/TaskBase/TaskOption（6 种 taskType） | — | **不复刻**，由 SOP 取代 |
| ⊘ | Checklist 模板库（TaskBase 集合） | — | 由 SOP 程序库取代 |
| ☐ | 工单挂载 SOP（锁定版本）作为执行依据 | 1 | ★ |
| ☐ | 工单执行实例 WorkOrderExecution | 1 | ★ |
| ☐ | 逐步执行：StepResponse（value/status/notes/photos/timestamp/operator） | 1 | ★ 覆盖原 taskType 的 文本/数值/勾选/检查/选项/抄表 |
| ☐ | 步骤照片证据 | 1 | |
| ☐ | 执行记录 + 签名 → 可审计 PDF | 1 | |
| ☐ | 抄表型步骤写回 Meter Reading | 2 | 依赖计量模块 |

### WO3. 工时与成本
| 状态 | 功能点 | 阶段 | 备注 |
|:--:|---|:--:|---|
| ☐ | 人工工时 Labor（计时器 RUNNING/STOPPED，hourlyRate，成本） | 1 | 套餐门控 ADDITIONAL_TIME(P6) |
| ☐ | 时间分类 TimeCategory | 1 | |
| ☐ | 完成时自动停止运行中计时 | 1 | |
| ☐ | 附加成本 AdditionalCost（CostCategory，includeToTotalCost） | 1 | 套餐门控 ADDITIONAL_COST(P6) |
| ☐ | 备件计划/消耗成本汇总（PartQuantity/PartConsumption） | 3 | 依赖库存 |
| ☐ | 工单总成本 = 人工 + 备件 + 附加 | 3 | |

### WO4. 请求 Requests（Phase 2）
| 状态 | 功能点 | 阶段 | 备注 |
|:--:|---|:--:|---|
| ☐ | 请求 CRUD（继承工单字段） | 2 | |
| ☐ | 请求审批 → 生成工单（双向关联） | 2 | |
| ☐ | 请求取消（原因） | 2 | |
| ☐ | 待审批列表 pending | 2 | |
| ☐ | 语音描述 audioDescription | 后期 | 低优先 |
| ☐ | 请求门户 REQUEST_PORTAL | 6 | 套餐门控 |
| ☐ | 请求表单字段配置 | 6 | |

### WO5. 预防性维护 PM（Phase 2）
| 状态 | 功能点 | 阶段 | 备注 |
|:--:|---|:--:|---|
| ☐ | PM 模板 CRUD（继承工单字段 + name） | 2 | 套餐门控 PREVENTIVE_MAINTENANCE |
| ☐ | 排程 Schedule（startsOn/frequency 天/endsOn/dueDateDelay/disabled） | 2 | |
| ☐ | 按排程自动生成工单（parentPreventiveMaintenance 回指） | 2 | 需后台调度器 |
| ☐ | PM 日历投影 | 2 | |
| ☐ | PM 挂载 SOP（模板传递给生成的工单） | 2 | ★ |
| ☐ | 后台调度器（生成 PM 工单 / 到期提醒） | 2 | |

---

## AS. 资产 / 位置 / 计量（Phase 1：资产+位置；Phase 2：计量+触发器）

### AS1. 位置 Locations
| 状态 | 功能点 | 阶段 | 备注 |
|:--:|---|:--:|---|
| ☐ | 位置 CRUD + 自引用树（parentLocation） | 1 | |
| ☐ | 地理坐标 longitude/latitude + 地址 | 1 | |
| ☐ | 关联 workers/teams/vendors/customers/files | 1 | |
| ☐ | 子位置查询 / 根位置 / mini 下拉 | 1 | |
| ☐ | 平面图 FloorPlan（图片 + area） | 后期 | 低优先 |

### AS2. 资产 Assets
| 状态 | 功能点 | 阶段 | 备注 |
|:--:|---|:--:|---|
| ☐ | 资产 CRUD + 自引用树（parentAsset） | 1 | |
| ☐ | 资产字段（serialNumber/model/manufacturer/power/warranty/inServiceDate/acquisitionCost…） | 1 | |
| ☐ | customId（A%06d）/ barcode（唯一）/ nfcId（唯一） | 1 | |
| ☐ | 按 barcode / nfc 查资产 | 1 | 移动端扫码用(P7) |
| ☐ | 资产状态 AssetStatus（7 值，UP/DOWN 映射） | 1 | |
| ☐ | 资产分类 AssetCategory | 1 | |
| ☐ | 关联 primaryUser/assignedTo/teams/vendors/customers/parts/files | 1 | |
| ☐ | 子资产查询 / 根资产 / mini | 1 | |
| ☐ | 停机 AssetDowntime（手动 + 自动） | 1 | |
| ☐ | 停机向上传播祖先 / 恢复向下传播后代 | 1 | |
| ☐ | 折旧 Deprecation（purchasePrice/rate/currentValue/usefulLife） | 后期 | |

### AS3. 计量 Meters（Phase 2）
| 状态 | 功能点 | 阶段 | 备注 |
|:--:|---|:--:|---|
| ☐ | 仪表 Meter CRUD（unit/updateFrequency，挂资产） | 2 | 套餐门控 METER |
| ☐ | 仪表分类 MeterCategory | 2 | |
| ☐ | 读数 Reading（校验 updateFrequency 节奏） | 2 | |
| ☐ | 按仪表查读数 | 2 | |
| ☐ | 工单抄表触发器 WorkOrderMeterTrigger（LESS_THAN/MORE_THAN，阈值） | 2 | |
| ☐ | 读数命中阈值 → 自动建工单 + 通知 | 2 | |

---

## IN. 库存与采购（Phase 3）

### IN1. 备件 Parts
| 状态 | 功能点 | 阶段 | 备注 |
|:--:|---|:--:|---|
| ☐ | 备件 CRUD（cost/quantity/minQuantity/unit/barcode/nonStock） | 3 | |
| ☐ | 备件分类 PartCategory | 3 | |
| ☐ | 关联 assignedTo/teams/customers/vendors/assets/files/PM | 3 | |
| ☐ | 库存扣减（consumePart，不足报错） | 3 | |
| ☐ | 低库存告警（< minQuantity 通知 assignedTo） | 3 | |
| ☐ | 消耗台账 PartConsumption（时间窗报表） | 3 | |
| ☐ | 多备件套件 MultiParts（kit，纯分组） | 3 | 套餐门控 CHECKLIST?→ PARTS |
| ☐ | mini 下拉 | 3 | |

### IN2. 采购 Purchase Orders
| 状态 | 功能点 | 阶段 | 备注 |
|:--:|---|:--:|---|
| ☐ | 采购单 CRUD（shipping 块 + 附加信息块） | 3 | 套餐门控 PURCHASE_ORDER |
| ☐ | 采购单分类 PurchaseOrderCategory | 3 | |
| ☐ | 采购行项目（PartQuantity 关联 PO） | 3 | |
| ☐ | 审批流 respond（approved → 逐行入库；REJECTED；不可重复批准） | 3 | |
| ☐ | 采购总成本计算 | 3 | |
| ☐ | 创建/审批通知 + 邮件 | 3/5 | |

### IN3. 供应商 / 客户
| 状态 | 功能点 | 阶段 | 备注 |
|:--:|---|:--:|---|
| ☐ | 供应商 Vendor CRUD（companyName/rate/type，M:N 资产/位置/备件） | 3 | |
| ☐ | 供应商自定义字段 | 6 | ✎ 复用 CustomFieldDef |
| ☐ | 客户 Customer CRUD（billing 块，billingCurrency，M:N） | 3 | |
| ☐ | 成本分类 CostCategory | 1/3 | 工单附加成本即用 |

---

## AN. 分析报表（Phase 4）

| 状态 | 功能点 | 阶段 | 备注 |
|:--:|---|:--:|---|
| ☐ | 工单：完成总览（total/complete/compliant/MTTA/avgCycleTime） | 4 | 套餐门控 ANALYTICS |
| ☐ | 工单：未完总览 / 按优先级·状态·资产·用户分布 | 4 | |
| ☐ | 工单：估时 vs 实际工时 | 4 | |
| ☐ | 工单：按主责人/完成人/优先级/分类的完成计数 | 4 | |
| ☐ | 工单：近 5 周计数与工时（合规/反应性） | 4 | |
| ☐ | 工单：成本与工时（labor/part/additional）、按日期成本 | 4 | |
| ☐ | 工单：按日期状态分布（历史重建） | 4 | 依赖审计历史 |
| ☐ | 资产：每资产工时&成本、停机 | 4 | |
| ☐ | 资产：MTBF / MTTR / 平均间隔 / 修复时长 | 4 | |
| ☐ | 资产：成本总览（RAV/总工单成本/总购置成本） | 4 | |
| ☐ | 资产：单资产总览（mtbf/mttr/downtime/uptime/totalCost） | 4 | |
| ☐ | 备件：消耗总览 / Pareto / 按资产·分类·WO分类 / 按月 | 4 | |
| ☐ | 请求：总览 / 按优先级 / 周期趋势 / 按分类 / 收到vs解决 | 4 | |
| ☐ | 人员：创建/完成数、某用户 14 天每日 | 4 | |
| ☐ | 仪表盘 UI + 日期范围筛选 + 缓存 | 4 | |

---

## 横切 / 其他

| 状态 | 功能点 | 阶段 | 备注 |
|:--:|---|:--:|---|
| ☐ | i18n（中文默认 + 多语言框架） | 0+ | Atlas 支持 8 语言 |
| ☐ | 数据导入 CSV（工单/资产/位置/备件/仪表） | 后期 | 套餐门控 IMPORT_CSV |
| ☐ | 数据导出 | 4 | |
| ☐ | 工作流自动化引擎（Workflow/Action/Condition，10 触发事件） | 5/后期 | 套餐门控 WORKFLOW |
| ☐ | API 访问（API_ACCESS） | 后期 | 套餐门控 |
| ☐ | Webhook | 后期 | 套餐门控 |
| ☐ | 健康检查 | 0 | |
| ☐ | 移动端 App（技师子集：工单/资产/位置/备件/仪表/请求/扫码/离线） | 7 | |

---

## 覆盖度统计（动态维护）

> ⚠️ **本矩阵逐行状态符号尚未随实现勾销**（仍多为 ☐），不可按字面统计。真实进度见下方
> **2026-06-01 实测核查汇总**，明细见 [剩余工作盘点](./2026-06-01-remaining-work-audit.md)。
> **不复刻（⊘）**：Atlas 扁平 Task/TaskBase/TaskOption/Checklist —— 由 SmartSOP SOP 取代（这是需求 #1）。
> **改造（✎）**：计费(Stripe 替 FastSpring)、授权(自有替 Keygen)、存储(S3 替 GCP/MinIO)、自定义字段(复用 CustomFieldDef)。

### 2026-06-01 实测核查汇总（按域 · 后端/前端分列）

| 域 | 后端 | 前端 | 备注 |
|---|:--:|:--:|---|
| 平台 认证/多租户/RBAC/用户/团队 | ~85% | 0% | 后端缺邮箱激活·密码重置·邀请；前端全缺（含登录页） |
| 平台 通知/邮件/文件 | ~95% | 0% | 后端完整(站内+邮件outbox+S3) |
| 工单核心 | ~60% | 0% | 缺工时成本(0%)·SLA·签名·反馈·归档·看板 |
| ★ SOP×工单执行（需求#1核心） | ~85% | 0% | 后端 attach/execution_view/update_step/完成门控/版本锁定 **已就绪**；缺执行PDF·签名·多媒体；前端执行界面全缺 |
| 位置 | ~100% | 0% | |
| 资产/分类/停机 | ~85% | 0% | 缺树停机传播·自动停机 |
| 请求 | ~98% | 0% | 审批→生单完整 |
| 预防性维护 PM | ~98% | 0% | 含调度器自动生单 |
| 计量/触发器 | ~98% | 0% | 含读数→阈值→自动建单 |
| 库存/备件/消耗/套件 | ~98% | 0% | 扣减·低库存·台账完整 |
| 采购/供应商/客户 | ~98% | 0% | 审批→入库完整 |
| 分析仪表盘 | ~90% | 0% | 4仪表板+MTBF/MTTR+CSV；前端无呈现 |
| Phase 6 商业化（订阅/计费/门控） | 0% | 0% | 仅 Company 预留字段 |
| Phase 7 移动端 | 0% | 0% | 后期 |
| SOP 模块（库/编辑器/导入/PDF） | ~95% | ~90% | 唯一前后端都完整 |

**综合：后端 phase0–5 ≈ 85%（含差异化核心）；前端 ≈ 20%（仅 SOP）；端到端可交付 ≈ 45–50%。
瓶颈在前端——"有引擎、没驾驶舱"。**
