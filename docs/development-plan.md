# 开发计划（Development Plan）

> 本文件是 Smart SOP 项目的总体路线图。所有阶段任务追踪、里程碑和验收标准都以本文件为准。
>
> 业务决策依据见 [feature-clarifications.md](feature-clarifications.md)。

## 1. 项目背景与目标

Smart SOP 是从 DPMS V2.0 `procedure` 模块剥离的独立产品，提供完整的结构化 SOP 管理能力，**去除**用户体系、审批工作流、组织架构和仪表关联，可独立部署使用。

> 注（Q242–Q245）：**审批模块本期仍不开发**，但应需求在 `tb_procedure_settings` 保留全局开关 `enable_approval_workflow`（默认 false），并在 publish 前预留内部 `ApprovalGate.check()` hook（本期 stub 放行、不改三态机、不加端点 / 字段）。属对 B3 的「最小预留」式受控反转，详见 [feature-clarifications.md §36](feature-clarifications.md)。

**核心交付目标**：

1. 完整保留 SOP 业务能力（CRUD、Word 转换、版本管理、PDF、文件夹、自定义字段、附件、审计）
2. **多版本数据模型**：upgrade-version 创建新记录，支持 rollback 与整 group deprecate / restore（不实现自动 diff，由用户手填 `version_update_notes`）
3. **标记模式 + 类型转换全套**：标记意图 → 应用按钮触发原子转换
4. **章节结构约束**：3 级嵌套、子节点类型互斥
5. 后端从 Django 迁移到 FastAPI（同步 + SQLAlchemy 2.0 + MySQL）
6. 前端沿用 Vue 3 + Element Plus + Pinia + Vite

## 2. 阶段路线图

总计 **9 个阶段**，预估 **32–42 个工作日**（多轮 grill 后工时上调；含 5 步导入向导、整 group 状态机、附件清理 daily task、程序复制、字段不可变约束、审计跨版本归属等）。

| 阶段 | 名称 | 工期 | 关键交付 |
|------|------|------|---------|
| Phase 0 | 项目初始化与基础设施 | ✅ 已完成 | 目录、文档、骨架配置 |
| Phase 1 | 核心数据层 | ✅ 已完成 | 10 张表的 ORM（8 业务 + 2 审计）、迁移、seed、乐观锁、审计 |
| Phase 2 | 文件夹模块 | ✅ 已完成 | 文件夹 CRUD + 树形 + 编号生成器 |
| Phase 3 | 程序基础 CRUD + 多版本骨架 | ✅ 已完成 | procedure_group_id / is_current / revision 机制 |
| Phase 4 | 编辑器核心（章节 + 步骤 CRUD + 互斥规则）| ✅ 已完成 | 章节树、互斥校验、编号自动生成、move/skip |
| Phase 5 | 标记模式 + 类型转换 | ✅ 已完成 | mark mode、apply-marks 原子事务、6 种 convert API |
| Phase 6 | Word 导入（5 步向导）| ✅ 已完成 | 文档解析后端 + scheduler；五步导入向导前端 + 编辑器图片直传接通 |
| Phase 7 | 版本管理 + 程序复制 | ✅ 已完成 | Fork / rollback / deprecate(整 group) / restore / copy / version_update_notes（后端 + 前端 UI）|
| Phase 8 | PDF 生成 | ✅ 已完成 | ReportLab Platypus 从零搭（11 模块）+ Noto CJK 子集 + 迭代收敛分页 + 前端逐页预览；两端点 pdf-layout/pdf-download |
| Phase 9 | 附件 + 自定义字段 + 设置 + 审计 + 收尾 | 5–6d | 附件 CRUD + 上限 + 磁盘清理 daily task；fields 不可变约束；审计跨版本归属 |

> **当前进展（2026-05-22）**：**M1 + M2 + M3 + M4 全栈达成；Phase 8（PDF 生成）全栈完成**。Phase 8 推翻过时清单（无 dpms 源、预览改前端渲染），从零按 pdf-rendering.md 搭 ReportLab 后端（11 模块 / 单引擎迭代收敛双产出 / 60s 硬超时 / Noto CJK GB2312 子集 + CID 回退）+ 前端逐页复刻预览弹窗；实现层决策落 §59（Q359-Q366）。后端 394 测试、前端 121 测试，两侧门禁全绿 + 独立子代理评审修复（H1 字体 / M1-M4 预览一致性 / LOW）。**下一里程碑 = Phase 9（附件 + 自定义字段 + 设置 + 审计 + 收尾）= M5 / Release 0.1.0 仅剩此一阶段**。

## 3. 阶段详细拆解

### Phase 0 — 项目初始化 ✅

**已完成**：

- [x] 顶层目录结构
- [x] 全套文档（10 份规范 + 决策汇编 + 编辑器规范）
- [x] 骨架配置（.gitignore / .editorconfig / docker-compose / requirements / package.json 等）
- [x] CI workflow 占位

### Phase 1 — 核心数据层（3–4d）

**目标**：把数据持久层、审计能力、序列号生成器建好。

**任务清单**：

- [x] `Base` 基类（UUIDMixin / TimestampMixin / SoftDeleteMixin + 可移植类型 DATETIME6/LONGTEXT + 命名规范）+ 基建（config / db / deps / logging Q329 / RequestIdMiddleware / errors）
- [x] 12 个 ORM 模型：Folder、FolderSequence、Procedure、ProcedureChapter、ProcedureStep、ProcedureAttachment、ProcedureField、ProcedureSettings、ProcedureAsset、ProcedureAssetReference（**10 业务**，原文档写「8 业务」已过时——Q189/Q197 增补 asset 两表，以 data-model.md §1「10 业务表 + 2 审计表」为准）+ FolderAuditLog、ProcedureAuditLog（2 审计）
- [x] Alembic 初始迁移（含 MySQL generated column 模拟 partial unique：active_unique_key / active_code_version / current_guard / draft_guard；dialect 守卫，SQLite 跳过；env.py include_object 防 alembic check 漂移）
- [x] `sequence_generator.py`：编码生成（select_for_update + 溢出回绕 + WARN；reset_period 固定 never Q251）
- [x] `audit_service.py`：审计日志写入封装（含 IP/UA；`X-Forwarded-For` 真实客户端 IP 解析 utils/net.py，配 `TRUSTED_PROXIES`，Q324）
- [x] `version_service.py`：版本号 + 变更日志写入封装（含 max_version_number 守卫）
- [x] `optimistic_lock.py`：If-Match 校验工具（IF_MATCH_REQUIRED 412 / VERSION_CONFLICT 409）
- [x] `seed.py`：「废止」系统文件夹 + Settings 单例 + 示例 ProcedureField（幂等）。**注**：模板库及三套样板已废除（§56/Q340），seed 不再建模板库文件夹（唯一系统文件夹 =「废止」）。
- [x] 各 service 的单元测试（覆盖率 96%，service 层 100%；含健康检查/中间件集成测试）

**验收**：✅ 单测 41 全过；ruff + mypy --strict 全过；迁移 upgrade/check/downgrade 通过（SQLite）。
> 待办（不阻塞）：MySQL 生成列 DDL 仅按构造正确（标准 MySQL 8 语法），未在真实 MySQL 跑通（本机 Docker daemon 未运行）；首次启动自动 migrate+seed 的钩子留待部署联调。

### Phase 2 — 文件夹模块（2d）

**任务**：

- [x] 后端：folders 路由（list/tree/options/CRUD/批量删/名称校验/前缀校验）
- [x] 后端：`folder_service`（深度校验、循环引用、full_path 缓存、硬约束删除）
- [x] 前端：文件夹管理页 + FolderTree 组件（M2 前端整段交付：树 + 创建/重命名/移动/删除 + 父级/前缀表单）
- [x] 集成测试：5 层嵌套、循环引用拒绝、删除非空拒绝、系统文件夹保护

**验收**：✅ 后端约束全受测（89 测试 / 98% 覆盖 / ruff + mypy --strict 全过）；UI 留待前端整段。
> 落地补充：文件夹**不走乐观锁**（Q18 仅 tb_procedure.revision，folder 模型/响应均无 revision）；PUT 支持改 parent_id（移动），无独立 move 端点；批量删除原子（Q20/Q325）；审计动作 create/update/**move**/delete/**batch_delete**（Q122），批量 new_value 含 {ids,count}（Q123）。
> 评审修复：叶子↔容器 prefix 往返复用既有 FolderSequence 行（folder_id unique，禁止重复插入）；leaf→container 停用序列。

### Phase 3 — 程序基础 CRUD + 多版本骨架（3–4d）

**任务**：

- [x] 后端：procedures 路由基础 CRUD（含 batch-delete / batch-move / library / detail）
- [x] 后端：创建程序时自动生成 code（前缀+序号）、初始 procedure_group_id、is_current=true、version=1、DRAFT、version_change_log create
- [x] 后端：状态机（DRAFT→PUBLISHED→ARCHIVED）+ transition API（v2+ publish 必填 notes，Q178）
- [x] 后端：乐观锁 If-Match（PUT / transition，复用 optimistic_lock；412/409）
- [x] 后端：is_current + status 守卫（PROCEDURE_READONLY / PROCEDURE_IS_CURRENT / PROCEDURE_STATUS_INVALID）
- [x] 前端：程序库列表（搜索/状态过滤/分页）+ 草稿列表 + 程序详情页（meta + 版本日志时间线 + 只读 banner）
- [x] 前端：状态切换按钮（发布/归档，带 If-Match）+ 创建程序表单（叶子选择器 + code 预览 + 用途级别）

**验收**：✅ 后端能创建程序、切换状态、并发 PUT 触发 409（131 测试 / 98% 覆盖 / ruff + mypy --strict 全过）。
> 落地补充：upgrade/rollback/deprecate/restore/copy/group 删除 = Phase 7（本期仅骨架）；详情 GET 嵌套树（chapters/steps/attachments）= Phase 4 填充，本期返空数组；新增全局 `RequestValidationError` 处理器统一 422→`VALIDATION_FAILED` 信封；`FOLDER_NOT_FOUND` 对齐错误码总表改用通用 `NOT_FOUND`（§23 未列前者）。
> 评审（无 CRITICAL/HIGH）修复：search 时 status 过滤仍生效（仅忽略 folder_id，Q278）。

### Phase 4 — 编辑器核心：章节 + 步骤 CRUD + 互斥（4–5d）

**最复杂阶段之一**。

**任务**：

- [x] 后端：chapters / steps CRUD（含 move-up/down/move/toggle-skip-numbering）
- [x] 后端：**Q25 子节点互斥校验** service（chapter/step/转换/标记/批量保存全路径覆盖）
- [x] 后端：**整树编号重算** service（§47）：trigger on save **即时**（Q310）；按 sort_order，skip_numbering 节点**不计入序号** + 子树静默（Q306）；内部 code 递归（L1=`N`/L2=`N.M`/L3=`N.M.K`），**L1 渲染层追加 `.0`**（Q305）；step 子码 = 父 chapter.code + seq，最深 4 段（Q308）；全自动不可手改（Q309）
- [x] 后端：章节嵌套 3 级校验（CHAPTER_DEPTH_EXCEEDED）
- [x] 后端：富文本总量校验（CONTENT_TOO_LARGE ≤5MB）；单图字节校验（IMAGE_TOO_LARGE）随编辑器图片直传端点 = Phase 6
- [x] 后端：chapter 节点 rich_content 写入校验（必须为空，否则 `CHAPTER_RICH_CONTENT_NOT_ALLOWED`）
- [x] 前端：ProcedureEditor 主框架（左树 + 右内容区）
- [x] 前端：章节树渲染、节点图标、编号显示、+/上下移/删除
- [x] 前端：新增按钮基于互斥规则的 disabled 逻辑
- [x] 前端：**chapter 节点详情面板（仅 title textarea + skip_numbering + 子节点列表展示，无 WangEditor）**
- [x] 前端：**content 节点详情面板（仅 WangEditor，无 title）**
- [x] 前端：WangEditor 集成（仅 content/step 用，警告块/签名栏/HoldPoint 按钮）。**图片直传依赖 assets 端点 = Phase 6，本期排除图片菜单**
- [x] 前端：步骤 12 型 input_schema UI（COMMON/CHECK/YESNO/NUMBER/METER/CHECKBOX/RADIO/UPLOAD/SIGNATURE/DATE/PHOTO/NONE，§40/Q261-Q262）+ note/caution/warning 三警示富文本（Q263）
- [x] 前端：拖拽 + 跨 parent 移动 + 实时互斥校验（含 3 级深度禁拖）
- [x] 前端：sessionStorage 自动保存 + 恢复（key=`procedure_editor_${id}`，1s debounce）
- [x] 前端：撤销/重做（50 步栈，快照式 + 同 tag 合并）
- [x] 前端：**编辑器顶栏**（面包屑 + 状态 chip + 未保存 chip + 主动作按钮组 + ⋮ 更多菜单；升级/丢弃/复制为 Phase 7 占位）
- [x] 前端：**程序详情折叠面板**（description/risk/quality/custom_values/version_update_notes 折叠区）
- [x] 前端：**右侧 3 tab 切换**（节点详情 / 附件 / 版本历史）
- [x] 前端：**树搜索框**（debounce 200ms 实时过滤 + `/` 快捷键聚焦 + 匹配 ancestor 路径保留）
- [x] 前端：**键盘快捷键集**（Ctrl+S / Ctrl+Z / Ctrl+Shift+Z / Delete / `/` / Esc）
- [x] 前端：**虚拟滚动**（useVirtualList 窗口化，覆盖节点 > 50）
- [x] 前端：**WangEditor 按需实例化**（详情面板按 selectedId keyed，切换节点销毁原实例）
- [x] 前端：**publish 检查列表弹框**（name/chapters/必填字段/未保存→全 ✓ 才能确认）
- [x] 前端：**read-only 模式**（is_current=false 或 status≠DRAFT 时全 disabled + 顶部 banner + /edit→/view 路由守卫）
- [x] 前端：**节点切换 dirty 保留**（store 集中状态，未保存修改跨节点切换不丢）
- [x] 后端：GET /procedures/{id} 一次性嵌套返回（嵌套章节树 + 平铺步骤 + active fields；attachments=Phase 9）
- [x] 后端：PUT /procedures/{id} 接受嵌套结构（脏节点 upsert + 显式删除 + 临时→真实 id 映射 + 最终态校验 + 乐观锁）

**验收**：能完整创建一个含多层章节 + 内容 + 步骤的程序；互斥规则全场景受测；编号正确。

### Phase 5 — 标记模式 + 类型转换（3–4d）

**任务**：

- [x] 后端：5 个转换 API（convert-to-step / convert-to-chapter / content-to-steps / batch-content-to-steps / convert-root-to-step）+ 1 个 410 stub（convert-to-content，§19 废弃）
- [x] 后端：转换前互斥规则 + 子节点非空校验（Q4 / Q6 / Q29）
- [x] 后端：apply-marks 原子事务接口（Q9，按 parent 最终态校验互斥）
- [x] 后端：mark-status 单点设置 API（不碰 review 态）
- [x] 前端：标记模式开关 + 三态切换 UI
- [x] 前端：批量选择（Shift+点击、跨 parent 拒绝、100 项上限）
- [x] 前端：应用标记按钮 + 确认对话框 + 错误处理
- [x] 集成测试：应用标记语义映射（chapter→step/content→steps/无操作/互斥拒绝/review 保留/同批多兄弟）

**验收**：标记 - 应用 - 转换全链路；任一违反互斥规则的事务回滚。

### Phase 6 — Word 导入（3–4d，含向导细化）

**任务**：

- [x] 后端：从 dpms 移植 `document_parser/` 完整包，并按 §19 重构改造：**每个非 heading 顶层块 → 独立 content 子节点**（不再汇入 chapter.rich_content）
- [x] 后端：FastAPI UploadFile 适配；30s 超时（线程执行器 Q345）；50MB 上限；MIME 双校验（扩展名 + OPC 嗅探 Q346）
- [x] 后端：`POST /uploads`（上传到临时区返 upload_token，纯文件系统 Q341）；`/parse` 改为 `{upload_token, parse_mode}`；24h 临时文件清理任务（独立 scheduler 进程每 1h 扫，Q331/§53）
- [x] 后端：`/parse/methods` `/parse` `/procedures/import` 接口
- [x] 后端：正文起点判定（§25.4/Q191）—— `first_styled_heading`（styles.xml 反查 4 级：标准名/中文同义词/outlineLvl/basedOn 上溯，且 ≥ toc_field_end）→ TOC field end → 启发式首标题 → 跳封面；**删除旧「最后 section break」规则**
- [x] 后端：标题**最多 3 级**（§25.3/Q190 二次修订回 3）；H4-6 / 更深编号压缩为 L3（恢复 Q35；title 保持纯文本 Q349）；编号引擎 3 级（import 复用 numbering_service）
- [x] 后端：图片抽到 `tmp/uploads/{token}/media/`（§25.2/Q193），import 时按 sha256 去重提升为 `tb_procedure_asset` + 写 `tb_procedure_asset_reference`；rich_content `<img src>` 改 asset URL；EMF/WMF 转 PNG（Q207，LibreOffice 优雅降级）；单图 ≤10MB
- [x] 后端：smart 模式置信度分级（§25.5/Q199）—— HIGH 免确认 / MEDIUM·LOW 标 `review`；编号分级字典 v4 + 误报抑制 + 等字号自适应；返回 `detected_patterns[]`（Q200）；两层词典 `heading_synonyms.yaml`（内置）+ `heading_style_map`（注入缝，DB 表延后 M4，Q344）
- [x] 后端：编辑器图片直传 `POST /procedures/{id}/assets`（multipart，sha256 去重即时入库，Q214）+ `GET /procedures/{id}/assets/{asset_id}` 资源服务
- [x] 后端：asset GC 后台任务（ref_count=0 ≥24h、行锁重核、行+文件同删；独立 scheduler 进程每日，Q197/Q333/§53）
- [x] 后端：空树检测 → `PARSE_NO_HEADINGS`（**仅 standard 模式或 smart 启发式也零命中时**，§25.7；standard 零标题走 `PARSE_TEMPLATE_INVALID` H001 error，Q350）
- [x] 后端：`/chapters/{id}/convert-to-content` 直接返 410 `CONVERT_TO_CONTENT_DEPRECATED`（复核既有）
> **前端整段已完成**（M4，2026-05-22）——以下前端任务与 Phase 7 版本管理 UI 同批在 M4 前端整段交付。

- [x] 前端：**5 步线性向导**（Element Plus Steps，indicator 可点已完成步骤）→ `views/procedures/ImportWizardView.vue` + `components/import/*`
  - step1 上传（拖拽 + 三档预警 20/40/50MB + .docx accept）→ `UploadStep.vue` + `utils/upload.ts`
  - step2 模式选择（standard / smart 默认 smart）→ `ModeStep.vue`（GET /parse/methods）
  - step3 校验报告 / 解析概览（standard 走模板规则；smart 走 metadata + warnings + review 预告）→ `ReviewReportStep.vue`
  - step4 树审查（中量编辑：title / skip / 删除递归 / 上下移；review 黄色提示；「重置为初始解析」按钮）→ `TreeReviewStep.vue` + `ImportTreeNode.vue` + 纯函数 `utils/importTree.ts`
  - step5 表单（name 默认文件名 + folder_id 仅非系统）→ `ImportFormStep.vue` + `utils/folders.ts`
- [x] 前端：sessionStorage 持久化（key=`procedure_import_wizard_v1`，含 created_at，24h 超期清理）→ `composables/useImportWizardPersistence.ts`
- [x] 前端：解析过程 spinner + 进度文字；30s 超时提示（client 45s 放宽让后端 504 PARSE_TIMEOUT 先到，Q352）
- [x] 前端：beforeRouteLeave 拦截已编辑状态（版本动作跳转走 leavingViaAction 绕过）
- [x] 前端：编辑器图片直传菜单接通（`RichTextEditor` customUpload → POST /procedures/{id}/assets，Q355；网络图片始终禁用）
- [x] 单元测试：parseApi / importTree / importWizardPersistence / uploadSize / ImportTreeNode（向导集成 e2e 与超大图片压缩留待 Phase 9 收尾）

**验收**：从向导 step1 → step5 → 提交跳转 /procedures/{new_id}；review 节点 UI 正确；图片自动压缩；24h 超期自动清。

### Phase 7 — 版本管理 + 程序复制（3–4d）

**任务**：

- [x] 后端：状态机校验（DRAFT/PUBLISHED/ARCHIVED 单向；非法转换返 `PROCEDURE_STATUS_INVALID`）
- [x] 后端：`/procedures/{id}/transition`（v2+ 发布须 version_update_notes，否则 `VERSION_UPDATE_NOTES_REQUIRED`）
- [x] 后端：upgrade-version（fork 新 DRAFT 版，深拷贝 chapters/steps 树 + 重算编号；附件元数据复制=Phase 9）
- [x] 后端：rollback（fork 自 ARCHIVED target，reason 必填，预填 notes）
- [x] 后端：deprecate（**整 group**：所有版本 ARCHIVED + 移「废止」+ 记 deprecated_from_folder_id；reason 必填；deprecated_by 恒 NULL=全匿名 Q322）
- [x] 后端：restore（整 group 移出废止 + 清废止标记 + fork 新 DRAFT；restore-preview；原 folder 已删则 target_folder_id 必填 `RESTORE_FOLDER_MISSING`）
- [x] 后端：DELETE is_current → `PROCEDURE_IS_CURRENT`；DRAFT v>1 当前版走「丢弃 DRAFT」特殊路径返 `{deleted_id,new_current_*}`（§22.11）
- [x] 后端：deprecated group 守卫（update/transition/upgrade/rollback/deprecate 一律 `PROCEDURE_DEPRECATED`；mark-read/move folder=Phase 9）
- [x] 后端：tb_procedure `version_update_notes` / `deprecated_from_folder_id` 列已在初始 schema；draft_guard 部分唯一（§31.3，MySQL 生成列 + service check-then-act）
- [x] 后端：`/procedure-groups/{group_id}/versions` 接口（含 notes 全文 + 100 字预览 + `?count_only`）
- [x] 后端：**程序复制** `/procedures/{id}/copy`（新 group、深拷贝树/custom_values；audit 记 copy_from）+ v1-DRAFT 整组硬删 `DELETE /procedure-groups/{group_id}`（拓扑删章节，Q177）
- [x] 前端：详情页头部 textarea「本次版本更新说明」（DRAFT 可改，其余只读）→ `ProcedureDetailView.vue` notes-card
- [x] 前端：版本动作 升级 / 回退 / 废弃 / 恢复 / 复制 按钮（reason 必填统一弹框 `VersionActionDialog.vue`，Q356/Q357/Q358）；编辑器顶栏占位接通（升级/丢弃/复制）；详情页 v1-DRAFT 整组删 + 丢弃草稿跳转
- [x] 前端：版本列表面板（GET /procedure-groups/{group_id}/versions）可展开 notes + 归档版回退入口 → `VersionListPanel.vue`（单测 `VersionListPanel.spec.ts` + `versionApi.spec.ts`）

**注**：不实现版本 diff 算法、版本对比 UI、差异导出。版本变更靠用户手填 notes，落入 PDF 修订记录页。

**验收**：upgrade → rollback → deprecate → restore → copy 五种流转全跑通；deprecated 守卫触发；DELETE is_current 拒绝；notes 正确写入与展示。

### Phase 8 — PDF 生成（3–4d）✅

> ⚠️ 原任务清单（dpms 移植 / SimSun-SimHei / `/pdf-preview` iframe+base64）**已被 Q234-Q237 推翻**：无 dpms 源（从零按 pdf-rendering.md 建）；预览改为**前端逐页复刻渲染**（非后端出图），仅保留两端点 `GET /pdf-layout`（分页 JSON）+ `GET /pdf-download`（ReportLab 静态 PDF）。实现层决策见 §59（Q359-Q366）。

**任务**（实际落地）：

- [x] 后端：从零搭 `services/pdf/` 11 模块（ReportLab Platypus，单引擎迭代收敛双产出 pdf_bytes+layout，§59.3/Q361）
- [x] 后端：渲染数据快照 `RenderData` 解耦 ORM/Session（线程池跑 60s 硬超时不踩 SQLAlchemy 线程边界，§59.4/Q362）
- [x] 后端：内置开源 **Noto CJK** GB2312 子集到 `app/assets/fonts/`（`NotoSerifSC`=宋体正文 / `NotoSansSC`=黑体标题·加粗，OFL）；缺失回退内置 CID `STSong-Light` + 生产降级告警；`registerFontFamily` 实现「加粗中文=黑体」（§59.1/Q359）
- [x] 后端：富文本 HTML→flowable 用 stdlib `html.parser`（特殊块 note/caution/warning-block + hold-point + signature-bar；表格缩放 / 嵌套表降级缩进 + 告警 / 图片等比缩放独占行 + 占位降级，§59.5/Q363）
- [x] 后端：封面（状态水印/签名栏/风险色块/`show_on_cover` 自定义字段）+ TOC（迭代收敛页码）+ 修订记录（仅里程碑过滤）+ 正文（章节·content·步骤·12 型执行占位符）+ 附件区段（用户「附件」章节或虚拟 `{N}.0` 章节）
- [x] 后端：`GET /{id}/pdf-layout`（`PdfLayoutOut` 分页契约，§59.2/Q360）+ `GET /{id}/pdf-download`（`{code}_Rev{version}.pdf`，`?debug=1` 返 layout JSON）
- [x] 前端：`PdfPreviewDialog` 全屏弹窗 —— 据后端 layout 逐页复刻封面/目录/修订/正文/附件（页码与下载版一致，Q235）+ 勾选签收 + `window.print()` 打印 + ANSI Z535 三色样式
- [x] 前端：纯函数模型 `pdfModel.ts`（编号/日期/执行文案/附件标注/封面字段解析/修订/逐页装配，便于单测）+ `api/procedures` 的 `fetchPdfLayout`/`downloadPdf`(blob)
- [x] 前端：详情页「PDF 预览」+「PDF 下载」按钮（`is_current` 显隐）

**验收**：✅ 能为任意程序生成含封面/目录/修订/正文/附件的 PDF，中文（含加粗=黑体）正常，三色警示·hold-point·签名栏渲染正确；预览与下载页码一致。后端 394 测试（pdf 53：fonts/context/html_render/sections/engine/engine_errors 单测 + 6 集成）；前端 121 测试（pdfModel 16）；后端 ruff+format+mypy --strict + 前端 lint+typecheck+build 全绿。独立子代理评审：必修 H1（黑体字体未就位）+ 中等 M1-M4（前端预览与下载不一致）+ LOW 全部修复。

### Phase 9 — 附件 + 自定义字段 + 设置 + 审计 + 收尾（5–6d）

**任务**：

- [x] 后端：附件 CRUD（multipart 上传、本地存储、软删保留文件）+ 限制（单文件 ≤50MB、单 procedure 数量 ≤30、总大小 ≤200MB）
- [x] 后端：upgrade-version / rollback / copy 时附件元数据复制；rollback 继承 target 的而非 current
- [x] 后端：**scheduler 进程 + 3 个清理任务**（独立 APScheduler 进程 replicas=1，Q331/§53）：附件磁盘清理 daily（扫 storage_path 引用计数 0 + 软删 ≥ 30 天 → 文件先删 + 行文件同删）、asset GC daily、临时上传清理 1h；各任务 CLI `python -m app.tasks.<name> --once`
- [x] 后端：fields CRUD + 批量 API（update-status / batch-delete / reorder / options）
- [x] 后端：fields 不可变约束（`field_type` / `key` 修改返 IMMUTABLE 错误码）
- [x] 后端：自定义字段值校验接线（Q367/Q368）：create / update / 编辑器整批保存校验已填值格式（require_check=False，草稿可缺必填）；发布 transition→PUBLISHED 强制必填（require_check=True）。2026-05-24 补接 `field_service.validate_values`（此前函数已写但无调用点）
- [x] 后端：options 软代理（archived）实现
- [x] 后端：settings GET / PUT（单例）
- [x] 后端：审计日志接口（folders / procedures，过滤 target_id / action / date_range / ip_address / procedure_group_id；procedure 表加 procedure_group_id 列）
- [x] 前端：附件管理 UI（上传 / 列表 / 下载 / 删除，含上限提示）
- [x] 前端：自定义字段管理页 + 「已废弃字段」折叠区在程序详情（2026-05-24 补 `ProcedureDetailsPanel` 折叠区：拉归档字段定义贴标签、`collectDeprecatedFieldValues` 派生只读历史值）
- [x] 前端：自定义字段管理页（列表 / 增删改 / 排序 / 批量）
- [x] 前端：编辑器中渲染自定义字段表单
- [x] 前端：全局设置页
- [x] 前端：审计日志列表（folders / procedures 各一页）
- [x] 文档：补 `architecture.md` 与 `operations-runbook.md`
- [x] CI：测试矩阵（`.github/workflows/ci.yml`：backend ruff format/lint + mypy + pytest≥80%；frontend eslint + typecheck + vitest + build。单版本 Py3.11/Node20，无多版本 matrix）

**验收**：所有 P0 功能 e2e 走通；测试覆盖率达标；文档完整。

## 4. 里程碑

| 里程碑 | 累计工期 | 包含阶段 | 状态 |
|--------|---------|--------|------|
| M1 — 数据层稳定 | T+4d | Phase 1 | ✅ |
| M2 — 文件夹 + 程序骨架可用 | T+10d | Phase 2, 3 | ✅ |
| M3 — 编辑器核心 + 标记模式可用 | T+18d | Phase 4, 5 | ✅ |
| M4 — Word 导入 + 版本管理可用 | T+25d | Phase 6, 7 | ✅ |
| M5 — PDF + 收尾 = Release 0.1.0 | T+38d | Phase 8, 9 | ✅ |

> T 为项目正式启动日（Phase 1 启动日，已扣除 Phase 0）。

## 5. 风险与对策

| 风险 | 概率 | 影响 | 对策 |
|------|-----|-----|------|
| **互斥规则在前后端不一致** | 中 | 高 | 后端 service 为权威，前端调用前预校验仅用于 UX，最终以后端返回为准 |
| **标记模式 apply 失败导致 UI 与 DB 状态不一致** | 中 | 中 | apply-marks 后端原子事务，失败前端重载整树状态 |
| **乐观锁触发频繁** | 中 | 中 | 提供「加载远程版本」一键解决；前端 sessionStorage 保留本地草稿 |
| **多版本数据膨胀** | 中 | 低 | upgrade-version 浅复制（附件元数据复用 storage_path）；定期归档 |
| **PDF 中文字体缺失** | 低 | 高 | 字体打包进镜像 + 测试用例验证 |
| **跨版本附件 storage_path 引用悬挂** | 低 | 中 | 软删后保留磁盘文件；后台脚本定期检查孤儿文件 |
| **Word 智能解析对极不规范文档识别率低** | 高 | 中 | 提供审查 UI 兜底；标记 review |
| **章节编号实时重算性能** | 低 | 低 | 单趟 O(n) 内存重算（Q310 即时 / Q338）；软上限 ~2000 节点非阻断提示；无需分批 |
| **WangEditor 与 PDF 渲染差异** | 中 | 中 | 提供「PDF 预览」让用户上线前验证 |
| **全匿名接口被恶意刷写** | 低 | 中 | 受控内网为硬前提（Q322）；nginx 分桶限流补齐 uploads / 写 / 读（Q323）；破坏性操作软删 + restore + 审计兜底（Q325）|

## 6. 待决策事项（追加）

| 项 | 当前状态 | 决策时机 |
|---|---------|---------|
| 多 tab 同时编辑同一程序的协调机制 | **按设计不做**（Q335）| 乐观锁 409 + per-tab sessionStorage 仲裁；真实冲突频发再议 |
| 实时协作编辑（多人同时） | 不在范围 | 远期，不立项 |
| 编辑器自动保存到后端（非 session）| **按设计不做**（Q336）| 显式保存 + sessionStorage 恢复；数据丢失反馈再议 |
| 附件预览（除图片外）| 不在范围 | 远期，不立项 |
| 程序导出 Word | 不在范围 | 远期，不立项 |
| auto_archive_days 定时任务实现 | **0.1.0 不实现**（Q337）| 未来 §53 scheduler 第 4 任务接入；DB 字段 / Q259 隐藏维持 |

## 7. 工时记录与变更

> 每完成一个阶段后追加一行。

| 阶段 | 计划工时 | 实际工时 | 完成日期 | 备注 |
|------|---------|---------|---------|------|
| Phase 0 | 1–2d | 1d | 2026-05-19 | 文档比预期多写两份（feature-clarifications + editor-behavior）|
| Phase 1 | 3–4d | ~0.5d | 2026-05-21 | 12 表 ORM + 迁移 + 4 service + seed；41 测试/96% 覆盖；ruff+mypy strict 全过。发现并修正 4 处评审项（compute_diff 漏删键、cascade 与软删冲突、seed 漏 is_active、step↔chapter back_populates）|
| Phase 2（后端）| 2d | ~0.4d | 2026-05-21 | folder_service + 路由 + schemas；89 测试(新增48)/98% 覆盖；ruff+mypy strict 全过。独立评审无 CRITICAL/HIGH；修 4 项（序列往返 unique、move/batch_delete 动作名、批量 {ids,count}、重算守卫）。**前端整段后延**（M2 策略：后端先行）|
| Phase 3（后端）| 3–4d | ~0.5d | 2026-05-21 | procedure_service + 路由 + schemas + 422 信封；131 测试(新增42)/98% 覆盖；ruff+mypy strict 全过。独立评审无 CRITICAL/HIGH；修 2 项（search+status、NOT_FOUND 对齐 canon）。upgrade/rollback/deprecate/restore/copy=Phase 7；**前端整段后延** |
| Phase 2+3（前端）| — | ~0.6d | 2026-05-21 | M2 前端整段：API 层 + 类型 + http 错误拦截器 + Pinia store + 布局/导航/路由 + FolderTree + 文件夹管理页 + 程序库/草稿/详情 + 创建弹窗 + 状态切换(If-Match)。修复工具链（eslint flat config + typescript-eslint v8，删旧 .eslintrc.cjs）。lint/typecheck/build 全过；vitest 8 测试通过。**M2 达成** |
| Phase 4（后端）| 4–5d | ~0.7d | 2026-05-21 | 编号引擎 numbering_service（§47，100% 覆盖）+ chapter_service（CRUD/Q25 互斥/3 级深度/§19 空正文/移动/递归软删）+ step_service（CRUD/12 型校验/移动）+ GET 嵌套树 + editor_service（PUT 整批保存：脏节点 upsert + 临时 id 映射 + 最终态校验 + 乐观锁）+ chapters/steps 路由。**前端整段后延**（M3 策略：后端先行）|
| Phase 5（后端）| 3–4d | ~0.4d | 2026-05-21 | conversion_service（5 转换 + 410 stub + 顶层 HTML 块拆分）+ mark_service（mark-status + apply-marks 原子，按 parent 最终态校验）。218 测试(新增88)/94% 覆盖；ruff+mypy strict 全过。独立评审修 C1(空元素吞内容)/H1(顶层实体丢失)/M1(误清 review 标记)。**前端整段后延** |
| Phase 4+5（前端）| — | ~1.0d | 2026-05-22 | M3 编辑器整段：node 类型 + chapters/steps/save/apply-marks API + utils（§47 客户端编号镜像 / Q25 / 回退文案）+ procedureEditor Pinia store（脏追踪 / 临时 id+id_map / 快照式撤销重做 / 客户端编号 / 立即后端转换·移动·删除·标记自动先存）+ 编辑器主框架（顶栏 / 只读 banner+路由守卫 / 3 tab / 详情折叠面板）+ 章节树（虚拟滚动 / 搜索 / 拖拽含 3 级深度禁拖 / Q25 disabled / 标记模式批量选择）+ chapter/content/step 详情面板（12 型 + 三警示 + 附件标记）+ WangEditor 按需实例化 + sessionStorage 自动保存恢复 + 键盘快捷键 + publish 检查弹框。lint/typecheck/build 全过；vitest 59 测试（新增 51）。独立评审修 C1/C2(标记模式临时 id 泄漏后端→404+静默丢标记)/H1(拖拽缺 3 级深度守卫)/H2(缺保存预校验)；M4(reload 折叠态丢失)。**M3 达成**。图片直传(assets)随 Phase 6。|
| Phase 7（后端）| 3–4d | ~0.6d | 2026-05-22 | version_flow_service：upgrade/rollback/deprecate/restore/copy + group 版本列表 + v1-DRAFT 整组硬删 + 深拷贝树（_clone_tree 重映射 + 重算编号）；procedure_service：丢弃 DRAFT 特殊路径 + deprecated 守卫 + get_or_404/resolve_leaf_folder 公开；schemas + procedures 路由(版本端点 + DELETE 200/204) + procedure_groups 路由。245 测试(新增 27：17 单测 + 8 集成 + 2 评审回归)；ruff+mypy strict+format 全过。独立评审修 C1/C2(fork 版本号须取 group 最大值+1 防 active_code_version 撞号)/H2(restore 补 draft 守卫+无 current 报错)/H3(整组硬删按真实树深拓扑删章节)；H1(deprecated_by 恒 NULL=全匿名)。附件元数据复制=Phase 9。**前端待补**（与 Phase 6 前端同批）|
| Phase 6（后端）| 3–4d | ~1.0d | 2026-05-22 | Word 解析器三阶段管线 `app/parser/`：opc（lxml 直遍历 body）+ styles（4 级反查 + classify_with_source）+ synonyms（内置 yaml）+ normalizer（顺序保真块流 + 段内多图 + 表格双 pass vMerge/gridSpan + 表内图 + SDT 递归 + TOC 域跟踪）+ body_start（§25.4 兜底链 + TOC 防陷阱）+ heading_detector（编号字典 v4/Q217 + 启发式封顶 0.84 + 等字号自适应 + detected_patterns）+ structurer（§19 章节树 + 置信度分级 + 3 级压缩）+ validators（template 最小集 + completeness 子集）+ images（sha256/尺寸/emf-wmf→png 优雅降级）。服务：asset_service（去重落盘 + 直传 Q214 + 引用重建 + GC 行锁 grace）+ upload_service（双校验 + 文件系统 token + 临时图）+ parse_service（线程执行器 30s 超时）+ import_service（建树 + 临时图提升 + 复用编辑器最终态校验）。端点：/uploads /uploads/{token}/media /parse/methods /parse /procedures/import /procedures/{id}/assets(直传+服务)。tasks：cleanup_uploads + asset_gc + scheduler(APScheduler) + CLI --once；docker-compose scheduler 接线 + 共享 storage 卷。**341 测试(新增 96：parser 52 单测 + asset/upload/parse 20 + tasks 5 + 集成 12 + 评审回归 3 + 既有补)；91% 覆盖；ruff+mypy strict+format 全过。** 决策落 §57/Q341-Q350。独立评审修 H1(import 复用 `_validate_and_recompute_levels` 防绕过 3 级/Q25)/M1(sha256 查找加 FOR UPDATE)/M2(mtime 回退 UTC)/M3(临时图 404)/L3(docstring)；L1/L2 匿名系统下记录不改。**前端整段后延**（M4 前端同批：Phase 6 五步向导 + Phase 7 版本管理 UI）|
| Phase 6+7（前端）| — | ~1.0d | 2026-05-22 | M4 前端整段：**Phase 6 五步导入向导** `ImportWizardView` + `components/import/*`（UploadStep 三档预警 / ModeStep / ReviewReportStep 三态 / TreeReviewStep+ImportTreeNode 中量编辑+review 黄标+重置 / ImportFormStep）+ 纯函数 `utils/importTree`（不可变树操作 + toImportNodes 清 review）+ `utils/upload`(分档)+`utils/folders`(叶子采集)+ `useImportWizardPersistence`(sessionStorage 24h)+ 路由 `/procedures/import` + 库入口；解析两步式（/uploads→/parse，client 45s 让后端 504 先到）。**编辑器图片直传接通** `RichTextEditor` customUpload→/procedures/{id}/assets（仅 full+procedureId+可编辑；网络图禁用）。**Phase 7 版本管理 UI**：`VersionActionDialog`(reason/folder/name 配置驱动)+`VersionListPanel`(版本列表+展开 notes+归档版回退)+ `ProcedureDetailView` 整合（头部更新说明 textarea / 升级·废弃·恢复·复制·回退·删除 按状态显隐 / v1-DRAFT 整组删 / 丢弃草稿跳转）+ `EditorTopBar` 占位接通(升级/丢弃/复制)+`ProcedureEditorView`(版本动作处理 + leavingViaAction 绕过守卫)+ `api/procedures` 版本动作函数(无 If-Match)+`api/parse`+ 类型扩展。决策落 §58/Q351-Q358。**前端 105 单测(新增 46：parseApi 6 / importTree 8 / importWizardPersistence 6 / uploadSize 7 / versionApi 10 / ImportTreeNode 5 / VersionListPanel 4)；lint/typecheck/build/vitest 全绿。** 独立评审无 CRITICAL，修 H1(解析超时话术与 45s 不自洽)/M1(详情页删除按钮收窄+接通 v1-DRAFT 整组删)/M2(动作函数补 catch 防未处理 rejection)/M3(编辑器 key 含只读态)/L2(updateNode 严格不可变)/L4(移除文件清向导进度)；LOW XSS(全匿名系统下可接受，留 DOMPurify 纵深防御)。**M4 达成（全栈）**。|
| Phase 8（全栈）| 3–4d | ~1.0d | 2026-05-22 | **PDF 生成全栈**（推翻过时清单：无 dpms 源、预览改前端渲染、仅 pdf-layout/pdf-download 两端点）。**后端** `services/pdf/` 11 模块从零搭：fonts(Noto CJK GB2312 子集 NotoSerifSC 宋体+NotoSansSC 黑体/OFL，registerFontFamily 加粗中文=黑体，缺失回退 CID+告警)+constants+context(RenderData 快照解耦 ORM/预取 asset 字节)+styles(缓存)+html_render(stdlib html.parser：三色块/hold/签名/表格降级/图片占位)+flowables+sections(封面/TOC/修订/正文/12 型占位符/附件区段，编号 render-only `.0`)+document(BaseDocTemplate+3 PageTemplate+afterFlowable 收页号+页眉页码 P/T+水印)+engine(迭代收敛单引擎双产出 pdf_bytes+layout，60s ThreadPoolExecutor 硬超时)+layout(PdfLayoutOut)+errors；schemas/pdf + procedures 路由两端点(pdf-download `{code}_Rev{version}.pdf`，?debug=1 返 layout)。**前端** PdfPreviewDialog(全屏逐页复刻+勾选签收+window.print 打印+ANSI Z535 三色)+纯函数 pdfModel.ts(编号/执行文案/封面字段解析/附件标注/逐页装配)+api fetchPdfLayout/downloadPdf+详情页 PDF 预览/下载按钮。决策落 §59/Q359-Q366。**后端 394 测试(新增 ~59：pdf 单测+6 集成)；前端 121 测试(pdfModel 16)；后端 ruff+format+mypy strict + 前端 lint+typecheck+build 全绿。** 独立子代理评审修 H1(黑体 NotoSansSC 未就位→生产加粗中文回退；补字体子集+缺失告警)/M1(预览缺附件清单区段)/M2(FieldOut 缺 show_on_cover+封面字段未解析 label)/M3(步骤跨页保护：决策仅标题 keepWithNext，整步 KeepTogether 推迟以保页码追踪/Q365)/M4(附件标注裸显 kind)/L5(水印 alpha 对齐)/L6(修订说明换行→`<br/>`)。**Phase 8 达成（全栈）**。|
| Phase 9（全栈）| 5–6d | ~1.5d | 2026-05-22 | 后端：fields CRUD+不可变约束+options软代理+settings单例+审计日志查询接口+CSV导出+Alembic迁移(revision列)。前端：附件管理UI(多文件上传/下载blob/删除+告警)+自定义字段管理页(CRUD/排序/批量/归档)+编辑器自定义字段类型分发控件+全局设置页(If-Match乐观锁)+审计日志双tab页(过滤/分页/CSV导出)+ProcedureDetailsPanel只读标签显示修复。文档：architecture.md+operations-runbook.md。前端 lint+typecheck+build 全绿。**M5 达成，Release 0.1.0 就绪。** |
