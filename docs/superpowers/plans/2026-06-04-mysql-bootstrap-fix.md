# MySQL bootstrap 修复 + 集成验证地基 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans（或 subagent-driven-development）。步骤用 checkbox（`- [ ]`）跟踪。本轮含**发现-修复迭代**（Task 3）：MySQL 障碍逐个暴露，非一次写完。

**Goal:** 让全新 MySQL（≥8.0.13）库 `alembic upgrade head` 整链跑通——清除 TEXT/JSON 字面 `server_default`（37 列 + 历史迁移 DDL）这道已知首障，迭代修到整链通；加防回归护栏；搭 env-gated MySQL 集成验证入口（SKIP LOCKED/取号并发 + SOP 硬化迁移）。

**Architecture:** 招式已实证——`server_default=sa.text("('')")` 在 MySQL/SQLite 都发 `DEFAULT ('')`（带括号表达式默认，MySQL 接受）。测试库仍 SQLite `create_all`；MySQL 验证为 env-gated 旁路。改写历史迁移安全（MySQL 从未 bootstrap、无已部署状态）。

**Tech Stack:** SQLAlchemy + Alembic（双方言）+ pytest + 本机 MySQL 9.6（Homebrew，root 空密码）。

设计依据：`docs/superpowers/specs/2026-06-04-mysql-bootstrap-fix-design.md`。

---

## 契约（全程以此为准）

- TEXT/JSON 列默认值招式：`server_default=sa.text("('')")` / `("'{}'")` / `("'[]'")`（**括号不可省**）。String 列不动。
- 权威判据：全新 MySQL 库 `alembic upgrade head` **整链成功**（非 grep 数对）。
- SQLite 后端 `pytest` 全量绿、ruff/format/mypy 净、`alembic heads` 单 head（`sop_tenancy_hardening`）不变、迁移往返绿。
- 不改业务语义/列类型/nullable/约束；默认值语义不变。
- 防回归：单测断言 metadata 无字面 TEXT/JSON `server_default`。

---

## 环境准备

```bash
brew services start mysql        # 本机 9.6；root 空密码
export MYV="mysql+pymysql://root@127.0.0.1:3306/sop_mysql_verify"
mysql -uroot -e "DROP DATABASE IF EXISTS sop_mysql_verify; CREATE DATABASE sop_mysql_verify CHARACTER SET utf8mb4;"
# 复现首障：DATABASE_URL=$MYV .venv/bin/alembic upgrade head  →  1101 @ initial_schema
```

---

## Task 1: 防回归护栏测试（先红）

**Files:** Create `backend/tests/test_no_literal_text_default.py`

- [ ] **Step 1: 写失败测试** —— 遍历 `app.models.Base.metadata` 所有表所有列；对 type 为 Text/JSON（或含 TEXT/JSON/BLOB）且 `server_default is not None` 的列，断言其 `server_default.arg` 是 SQLAlchemy `TextClause`（即表达式默认）而非裸字符串字面。当前 37 列为字面 → **FAIL**，断言信息列出违规列名（便于 Task 2 核对）。

```python
from sqlalchemy.sql.elements import TextClause
from app.models import Base

def test_no_literal_server_default_on_text_json_columns():
    bad = []
    for t in Base.metadata.sorted_tables:
        for c in t.columns:
            tn = type(c.type).__name__.upper()
            if ("TEXT" in tn or "JSON" in tn or "BLOB" in tn) and c.server_default is not None:
                arg = getattr(c.server_default, "arg", None)
                if not isinstance(arg, TextClause):
                    bad.append(f"{t.name}.{c.name}")
    assert not bad, f"TEXT/JSON 列须用表达式默认 sa.text(\"('')\")，以下仍为字面: {bad}"
```

- [ ] **Step 2: 跑红** `.venv/bin/python -m pytest tests/test_no_literal_text_default.py -q` → FAIL，记录 37 列清单。

---

## Task 2: 修 37 个模型列（字面 → 表达式默认）→ 护栏转绿

**Files:** Modify `backend/app/models/*.py`（按 Task 1 输出的列清单逐文件改）

- [ ] **Step 1: 逐列改** —— 每个违规列 `server_default="…"` → `server_default=sa.text("('…')")`：空串用 `("'')")` 即 `sa.text("('')")`；`params` 用 `sa.text("('{}')")`；`disabled_types` 用 `sa.text("('[]')")`。`default=`（Python 端）不动。按各文件既有 import 习惯引入 `text`（`from sqlalchemy import text` 则用 `text("('')")`，或 `import sqlalchemy as sa` 则 `sa.text(...)`）。

> 以 Task 1 的运行时清单为准，不靠 grep；改完重跑护栏直到列清单清零。

- [ ] **Step 2: 护栏转绿** `.venv/bin/python -m pytest tests/test_no_literal_text_default.py -q` → PASS。
- [ ] **Step 3: SQLite 冒烟** `.venv/bin/python -m pytest tests/unit/test_seed.py tests/integration/test_folders.py -q -p no:cacheprovider` → 绿（`create_all` 在 SQLite 仍正常，`DEFAULT ('')` 合法）。
- [ ] **Step 4: 门禁** `.venv/bin/ruff check app tests && .venv/bin/ruff format --check app tests && .venv/bin/mypy app`。
- [ ] **Step 5: Commit** `git commit -m "fix(mysql): 37 个 TEXT/JSON 列 server_default 字面→表达式默认（MySQL 1101）+ 防回归护栏"`

---

## Task 3: 迁移 DDL 同改 + 迭代修到 MySQL upgrade head 整链通（发现-修复循环）

**Files:** Modify `backend/alembic/versions/*.py`（initial_schema 为主 + 重建表迁移 + 任何 add Text 默认列的迁移）

> 这是本轮主要工作量与不确定性来源：TEXT 默认是已知首障，修掉后 `upgrade head` 会推进到下一个迁移，可能暴露更多 MySQL-only 障碍。逐个发现、修复、重试，直至整链通。

- [ ] **Step 1: 改 initial_schema 的 TEXT 字面默认** —— `20260521_2033_initial_schema.py` 里 `sa.Text(), … server_default=''`（及 `'{}'`/`'[]'`）→ `server_default=sa.text("('')")` 等。`downgrade` 若有重建路径同改。

- [ ] **Step 2: MySQL 重试 upgrade head** ——
```bash
mysql -uroot -e "DROP DATABASE IF EXISTS sop_mysql_verify; CREATE DATABASE sop_mysql_verify CHARACTER SET utf8mb4;"
DATABASE_URL="mysql+pymysql://root@127.0.0.1:3306/sop_mysql_verify" .venv/bin/alembic upgrade head 2>&1 | tail -25
```
推进到下一个失败迁移。

- [ ] **Step 3: 发现-修复循环** —— 对每个新暴露的 MySQL-only 障碍：
  - **TEXT 默认（其它迁移）**：同 Step 1 招式。
  - **生成列**（`tb_procedure` 的 `current_guard`/`draft_guard`/`active_code_version` 等 `op.execute(... GENERATED ...)`）：MySQL 应原生支持；若 SQL 方言写法有差异（如 `STORED` 语法），按 MySQL 语法修，必要时 `.with_variant` 分方言。
  - **索引键长 / charset**（utf8mb4 下 VARCHAR 索引 > 3072 字节、ENUM、collation）：按报错最小化修，仅在阻断 `upgrade head` 时才动；记录每处改动原因。
  每修一处，回 Step 2 重试，直到 `alembic upgrade head` 打印到 `sop_tenancy_hardening` 且无错。

- [ ] **Step 4: 反向尽力验证** —— `DATABASE_URL=$MYV .venv/bin/alembic downgrade base` 不报致命错误（删除性反向，尽力；记录任何不可逆点）。

- [ ] **Step 5: env-gated MySQL bootstrap 测试** —— `backend/tests/test_mysql_bootstrap.py`：仅当 `TEST_MYSQL_URL` 环境变量存在时运行——对该 URL 指向的全新库跑 `command.upgrade(cfg, "head")` 断言成功、`alembic heads` 单 head；缺省 `pytest.skip`（CI 无 MySQL 不挂）。

- [ ] **Step 6: 门禁 + Commit** `git commit -m "fix(mysql): 历史迁移 TEXT 默认改表达式 + 迭代修通 MySQL alembic upgrade head（含 <后续障碍清单>）"`（commit message 列出 Step 3 实际遇到并修的障碍）。

---

## Task 4: SQLite 全量回归 + 单 head 守护

- [ ] **Step 1: 后端全量** `.venv/bin/python -m pytest -q -p no:cacheprovider` → 全绿（迁移 DDL 改动后，`test_migration_*` 往返仍须绿）。
- [ ] **Step 2: 门禁** ruff/format/mypy 净；`.venv/bin/alembic heads` → 仍 `sop_tenancy_hardening` 单 head（本轮不新增迁移）。
- [ ] **Step 3: Commit（如有格式化）** `git commit -m "chore(mysql): bootstrap 修复收尾" || echo 无改动`

---

## Task 5: 集成验证地基（env-gated）+ 红线并发点验证

> bootstrap 通后，针对 SQLite 测不到的红线补 MySQL 实跑验证。可本轮后段或紧邻后续；至少完成并记录结论。

- [ ] **Step 1: 批量解析并发（SKIP LOCKED/租约）** —— 在 MySQL 上构造多 worker 并发 claim 同一 batch 的 item，验证 `batch_parse_service`/`batch_apply_service` 的 SKIP LOCKED 取件不重不漏（见 [[batch-word-parsing-mvp]]）。记录结论。
- [ ] **Step 2: 并发取号** —— folder sequence 及其它 Sequence scope 在 MySQL 并发下取号唯一、无跳号竞态。记录结论。
- [ ] **Step 3: SOP 硬化迁移在 MySQL** —— 确认 `sop_tenancy_hardening` 在 MySQL：17 表 `MODIFY company_id NOT NULL` 成功、4 处复合唯一就位、`tb_procedure` 生成列 + 其 UNIQUE 保留（offline `--sql` 复核 + 实跑断言）。记录结论。
- [ ] **Step 4: 记录** 把"MySQL 集成验证结论"写入轮次报告 + 更新 [[batch-word-parsing-mvp]]/[[smart-cmms-progress]] 的"MySQL 待手验"为"已验证（版本/范围）"。

---

## Task 6: 收尾

- [ ] **Step 1: 汇报** 新增/修改文件清单、SQLite 全量通过数、MySQL `upgrade head` 结论、Task 3 实遇障碍清单、Task 5 验证结论、遗留项。
- [ ] **Step 2: 环境清理** `mysql -uroot -e "DROP DATABASE IF EXISTS sop_mysql_verify"`；按需 `brew services stop mysql`。
- [ ] 不合并/不 push，等人工审查（除非另有指示）。

---

## Self-Review（执行后记录结论）

**Spec 覆盖**：§组件1 模型 → Task 2 ✓；§组件2 迁移 → Task 3 ✓；§组件3 护栏 → Task 1 ✓；§组件4 验证地基 → Task 5 ✓；§验收标准 → 分散 Task 2/3/4/5 ✓。

**执行注意**：
1. 括号招式 `sa.text("('')")` 不可写成 `("''")`（无括号 MySQL 仍拒）。
2. Task 3 是发现-修复循环，工作量取决于 TEXT 默认之后隐藏的 MySQL-only 障碍数；逐个修、每修重试 `upgrade head`。
3. 权威判据是 MySQL `upgrade head` 整链通，不是 grep 计数；模型与迁移须一致，漏改某迁移会卡在该迁移。
4. SQLite 测试用 `create_all`，但 `test_migration_*` 在 SQLite 跑特定迁移——迁移 DDL 改动后须确认其往返仍绿。
