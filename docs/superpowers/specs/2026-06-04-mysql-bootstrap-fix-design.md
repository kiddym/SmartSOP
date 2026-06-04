# MySQL bootstrap 修复（TEXT/JSON 字面默认 → 表达式默认）+ 集成验证地基 设计

> 「MySQL 集成验证专项」（[[cmms-execution-roadmap]] 第 2 步，上线红线）的**前置使能**轮次。验证批量解析 SKIP LOCKED/租约、各并发取号、SOP 硬化 NOT NULL/生成列 partial-unique 等"SQLite 测不到"的行为，前提是 schema 能在 MySQL 上建起来——而当前**整条迁移链在第一个迁移即失败**。本轮先清除这道根障碍。

## 背景（已实测复现）

- 本机 MySQL **9.6.0**（Homebrew，root 空密码）。`alembic upgrade head` 在第一个迁移 `1d3b3aad6681 initial_schema` 建 `tb_folder` 时报：
  `(1101, "BLOB, TEXT, GEOMETRY or JSON column 'full_path' can't have a default value")`。
- 原因：MySQL 对 TEXT/BLOB/JSON 列**只接受表达式默认值** `DEFAULT (<expr>)`，不接受字面 `DEFAULT '…'`；而模型/迁移用 `server_default="…"` 发的是字面值。
- 范围（已枚举）：**37 个 TEXT 列**带字面 `server_default`（35 处空串 `''` + 2 处 JSON-as-Text：`tb_notification.params='{}'`、`tb_notification_preference.disabled_types='[]'`）。String 列的 `DEFAULT ''` MySQL 接受，**不在范围**。
- 这些字面默认同时**烘焙在历史迁移 DDL** 中：主要在 `initial_schema`，外加少数"重建表"迁移（`20260524_0001_drop_alert_fields`、`20260525_0002_drop_expected_output` 等）会重新发出这些列定义。
- 影响面：测试库走 `Base.metadata.create_all`（SQLite），故 CI 从未暴露；**MySQL 路径实际从未成功 bootstrap**——这正是长期"MySQL 仅手验/待手验"遗留的根因（见 [[mysql-text-default-blocks-bootstrap]]、[[batch-word-parsing-mvp]]、[[atlas-parity-backfill]]）。

## 修复招式（已实证）

`server_default=sa.text("('')")` 在 **MySQL 与 SQLite 都**发出 `DEFAULT ('')`（带括号的表达式默认），MySQL 接受、SQLite 兼容。对照：
- `server_default=""`（字面）→ `DEFAULT ''` → MySQL 1101 拒。
- `server_default=sa.text("''")`（无括号）→ `DEFAULT ''` → 仍被拒。
- `server_default=sa.text("('')")`（**有括号**）→ `DEFAULT ('')` → ✅ 双方言通过（已 `CREATE TABLE … DEFAULT ('')` 实测 MySQL 9.6 接受）。

JSON-as-Text 两列：`sa.text("('{}')")`、`sa.text("('[]')")`。

> 关键：括号不可省。`text("('')")` 而非 `text("''")`。

## 设计决策

1. **改写历史迁移安全**：MySQL 从未成功 bootstrap，**无任何已部署 MySQL 库**应用过这些迁移；SQLite 测试走 `create_all` 而非迁移链（仅个别 `test_migration_*` 在 SQLite 跑特定迁移，`DEFAULT ('')` 在 SQLite 同样合法）。故直接编辑历史迁移文件的字面默认为表达式默认，不破坏任何已有状态。
2. **模型与迁移同改**：模型 37 列改 `sa.text("('…')")`（影响 `create_all` + 未来新迁移），历史迁移 DDL 同步改（影响 `upgrade head` bootstrap）。两者一致。
3. **迭代式清障**：当前只确证了**第一个**障碍（TEXT 默认）。修掉后 `upgrade head` 会推进到下一个迁移，可能暴露更多 MySQL-only 问题（生成列 `current_guard` 等、utf8mb4 索引键长、charset/collation、ENUM、`DATETIME(6)`）。本轮目标是**迭代修到 `alembic upgrade head` 在全新 MySQL 库整链跑通**，TEXT 默认是已知首障，后续障碍随发随修并记录。
4. **不改业务语义**：默认值语义不变（空串/空 JSON），仅改 DDL 表达形式；不动列类型、不动 nullable、不动既有约束。
5. **本轮不写新功能、不改 SQLite 行为**：纯 schema DDL 兼容性修复 + 验证地基。

## 组件与改动

### 1. 模型层（37 列）
`app/models/*.py` 中所有 `mapped_column(Text, default="…", server_default="…")` 的 `server_default` 字面 → `sa.text("('…')")`：
- 35 处 `server_default=""` → `server_default=sa.text("('')")`
- `notification.params`：`"{}"` → `sa.text("('{}')")`
- `notification_preference.disabled_types`：`"[]"` → `sa.text("('[]')")`
- `default=`（Python 端）保持不变（ORM 插入仍给值）。逐列加 `from sqlalchemy import text` 或 `sa.text`（按文件既有 import 风格）。

> 执行时以 `Base.metadata` 运行时枚举为权威清单（type 为 Text/JSON 且 server_default 非空），而非 grep，避免漏配格式各异的写法。

### 2. 迁移层（历史 DDL）
编辑发出这些字面默认的迁移文件，使 `upgrade()`（及相关 `downgrade()` 重建）对 TEXT 列用 `server_default=sa.text("('')")`：
- `20260521_2033_initial_schema.py`（主）
- 重建表迁移：`20260524_0001_drop_alert_fields.py`、`20260525_0002_drop_expected_output.py`，以及任何 `add_column` 了 Text 默认列的后续迁移。
- 权威判据：在全新 MySQL 库 `alembic upgrade head` 全链成功（非靠 grep 数对）。

### 3. 防回归护栏（新增测试）
- 单测：断言 `Base.metadata` 中**不存在** type 为 Text/JSON 且 `server_default` 为字面（非 `TextClause`）的列——防止未来新列再引入字面 TEXT 默认。
- （可选）一个 MySQL-gated 测试：当 `TEST_MYSQL_URL` 环境变量存在时，对全新 MySQL 库跑 `upgrade head` 断言成功；缺省 skip（CI 无 MySQL 时不挂）。

### 4. 集成验证地基（本轮交付"能验"，真正各项验证可同轮或紧邻后续）
bootstrap 通后，补一个轻量"MySQL 集成"测试入口（env-gated），覆盖 SQLite 测不到的红线：
- 批量解析 worker 的 SKIP LOCKED / 租约（`batch_parse_service`/`batch_apply_service`，见 [[batch-word-parsing-mvp]]）。
- 各并发取号点（folder sequence、其它 Sequence scope）。
- SOP 硬化迁移在 MySQL：NOT NULL + 4 处复合唯一 + `tb_procedure` 生成列 partial-unique 保留。
> 这些可作为本轮后段或下一轮；本轮的**硬交付**是 bootstrap 通 + 防回归护栏。

## 验证策略

- **MySQL**：`brew services start mysql`；`DATABASE_URL=mysql+pymysql://root@127.0.0.1:3306/<db>` 全新库 `alembic upgrade head` 全链通过；再 `downgrade base` 反向（尽力，确认无致命反向错误）。
- **SQLite 回归**：后端 `pytest -q` 全量保持绿（含 `test_migration_*` 往返）；ruff/format/mypy 净；`alembic heads` 单 head 不变。
- **双方言一致**：抽查若干表 `create_all` 在 MySQL 与 SQLite 均成功。

## 边界与非目标

- 不改业务逻辑、不改列类型/nullable/约束语义。
- 不把测试库切到 MySQL（仍 SQLite `create_all` 为主；MySQL 验证为 env-gated 旁路）。
- 不在本轮追求 MySQL 全量集成测试覆盖；先打通 bootstrap + 红线并发点验证地基。
- 不处理与 1101 无关的 MySQL 调优（索引/charset 仅在阻断 `upgrade head` 时才修）。

## 风险

1. **后续未知障碍**：TEXT 默认只是首障，`upgrade head` 可能在后续迁移再失败（生成列/索引键长/charset）。本轮按"迭代修到整链通"推进，工作量取决于隐藏障碍数——计划须容纳发现-修复循环。
2. **改写 21 个历史迁移**面广：逐处改字面→表达式，且 `downgrade` 的重建路径也要改；用 MySQL `upgrade head`+SQLite 往返双向守护。
3. **MySQL 9.6 vs 生产版本差异**：本机 9.6，若生产用 8.0.x，表达式默认（8.0.13+ 支持）均覆盖；记录最低支持版本 8.0.13。
4. **create_all 与迁移 DDL 漂移**：模型改了但漏改某迁移 → MySQL bootstrap 仍挂在该迁移；以 `upgrade head` 为准、不以 grep 为准。

## 验收标准

- 全新 MySQL（≥8.0.13，本机 9.6 实测）库 `alembic upgrade head` **整链成功**，无 1101 及后续致命错误。
- `Base.metadata` 无字面 TEXT/JSON `server_default`；防回归单测就位。
- SQLite 后端 `pytest` 全量绿、ruff/format/mypy 净、`alembic heads` 单 head 不变、迁移往返绿。
- （地基）env-gated MySQL 测试入口就位，至少覆盖批量解析 SKIP LOCKED/取号并发与 SOP 硬化迁移在 MySQL 的行为（本轮或紧邻后续完成并记录结论）。
