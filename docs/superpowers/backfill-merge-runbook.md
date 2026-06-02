# 补全分支合并 Runbook（Atlas parity backfill）

> 目的：把并行开发的多个补全分支**线性、无冲突**地合入 `main`，规避 alembic 多 head 陷阱。
> 适用：所有从同一 `main` 基线并行分叉、各自新增一个 alembic 迁移的补全分支。
> 维护：每合入一个分支后更新"当前 main 迁移 head"。

## 0. 背景与现状（2026-06-02）

多个补全分支均从 `main`（`104c3a2`，含 2A 工时成本）分叉、文件改动**互不相交**（已实证核对），但每个分支各新增一个 alembic 迁移，且开发期都把 `down_revision` 设为当时的 head `workorder_labor_cost`。这会在合并后造成 alembic **迁移树分叉（多 head）**——这是唯一需要人工协调的点，**不是 git 文件冲突**。

在飞分支与各自迁移：

| 分支 | 工作区 | 迁移文件 | revision | 开发期 down_revision |
|---|---|---|---|---|
| `feat/analytics-backfill` | 主 checkout | `20260602_0004_analytics_backfill.py` | `analytics_backfill` | `workorder_labor_cost` |
| `feat/asset-backfill` | `.claude/worktrees/asset-backfill` | `20260602_0005_asset_downtime_propagation.py` | `asset_downtime_propagation` | `workorder_labor_cost` |
| （未来）`feat/inventory-backfill` | 另开 worktree | 待定 | 待定 | `workorder_labor_cost` |

> `main` 当前迁移 head = `workorder_labor_cost`（2A）。

## 1. 核心规则

**先合入者保持原样；后合入者把它那个迁移的 `down_revision` 改指向"当前 main 的迁移 head"，使迁移链保持单一线性。**

每合入一个分支，"当前 main 迁移 head" 就前移到该分支的 revision，下一个待合分支据此 rebase。

## 2. 合并顺序（建议）

按"谁先完成且验收通过谁先合"。当前进度下分析分支领先，建议：

1. `feat/analytics-backfill`（revision `analytics_backfill`）
2. `feat/asset-backfill`（revision `asset_downtime_propagation`）
3. （未来）`feat/inventory-backfill`

顺序可变；规则（§1）与顺序无关，按实际完成情况套用即可。

## 3. 合并前每分支的验收门（在该分支的工作区内）

进入该分支工作区，确保：

```bash
cd <该分支 backend/>
.venv/bin/python -m pytest -q          # 全绿
.venv/bin/ruff check app/              # All checks passed
.venv/bin/mypy app/                    # no issues
```

- 该分支自身的迁移 unit 测试通过（验 DDL up/down/可重放）。
- subagent-driven 的最终 code review 已过、`finishing-a-development-branch` 已走。

## 4. 合并步骤

### 4.1 合入第 1 个分支（示例：analytics，无需改 down_revision）

```bash
# 在主 checkout（确保工作树干净、该分支已验收）
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP"
git checkout main
git merge --no-ff feat/analytics-backfill -m "Merge branch 'feat/analytics-backfill'"
```

- 预期：**干净合并，零 conflict**（与 main 的改动文件不相交）。
- 若 `git merge` 报 conflict → 信号：某分支越界改了不属于它的文件（scope creep）。**停下排查**，不要强合。

合并后：
```bash
cd backend && .venv/bin/python -m pytest -q   # 全量回归仍绿
.venv/bin/alembic heads                        # 应只有 1 个 head = analytics_backfill
```
更新本 runbook：当前 main 迁移 head = `analytics_backfill`。

### 4.2 合入第 2 个分支（示例：asset，需先 rebase down_revision）

**关键一步——改 down_revision：**

```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP/.claude/worktrees/asset-backfill"
# 编辑 backend/alembic/versions/20260602_0005_asset_downtime_propagation.py
#   down_revision: 由 "workorder_labor_cost" 改为 "analytics_backfill"（当前 main head）
```
把该文件中：
```python
down_revision: str | Sequence[str] | None = "workorder_labor_cost"
```
改为：
```python
down_revision: str | Sequence[str] | None = "analytics_backfill"
```
提交这一行改动：
```bash
git add backend/alembic/versions/20260602_0005_asset_downtime_propagation.py
git commit -m "chore(migration): rebase down_revision onto analytics_backfill for linear chain

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

再合入：
```bash
cd "/Users/yuming/Desktop/smart CMMS/SmartSOP"
git checkout main
git merge --no-ff feat/asset-backfill -m "Merge branch 'feat/asset-backfill'"
```

合并后验证：
```bash
cd backend
.venv/bin/alembic heads        # 仍只有 1 个 head = asset_downtime_propagation
.venv/bin/alembic history | head   # 链应线性：
                               #   workorder_labor_cost -> analytics_backfill -> asset_downtime_propagation
.venv/bin/python -m pytest -q  # 全量回归绿
.venv/bin/ruff check app/ && .venv/bin/mypy app/
```
更新本 runbook：当前 main 迁移 head = `asset_downtime_propagation`。

### 4.3 第 3+ 个分支

重复 §4.2：把其迁移 `down_revision` 改指向"当前 main 迁移 head"，commit，`merge --no-ff`，验证单 head + 线性 + 回归。

## 5. 全链迁移验证（已知限制）

`alembic upgrade head` 从 base 全链重放**受既有 `initial_schema` 的 TEXT server_default 问题阻塞**（与各补全迁移无关，历史遗留）。因此合并后**不以全链 upgrade 为验收口径**，改以：

- `alembic heads` 单 head（无分叉）；
- `alembic history` 链线性；
- 每个补全迁移自带的 unit 测试（importlib + MigrationContext，最小 fixture 验 DDL up/down/可重放）通过；
- 全量 pytest（SQLite `create_all`，不走 alembic）绿。

MySQL 生产全链迁移仍待按实际版本以最小 fixture 手验（沿用既有声明）。

## 6. 合并后收尾

- 不自动 `push`：约定 `--no-ff` 合入 main、**本地暂不 push**，由人决定推送时机。
- 更新记忆 `atlas-parity-backfill`（标记对应组已合入 main）与 `smart-cmms-progress`。
- 清理已合并的补全分支与其 worktree：
  ```bash
  git worktree remove .claude/worktrees/asset-backfill   # 已合并后
  git branch -d feat/asset-backfill
  ```
  （未合并/有独有提交的分支不删；删前 `git branch --merged` 确认。）
- 删除本 runbook 的临时 worktree/分支（合入或丢弃后）：
  ```bash
  git worktree remove .claude/worktrees/merge-runbook
  ```

## 7. 冲突自检清单（合并若不顺）

- `git merge` 报 conflict？→ 不该发生（文件不相交）。排查是否有 agent 越界改文件，定位冲突文件、人工核对，**勿盲目 `-X` 强合**。
- `alembic heads` 多于 1 个？→ 漏改某分支 down_revision；按 §4.2 补 rebase。
- `alembic history` 非线性/有分叉标记？→ 同上。
- 全量 pytest 合并后变红、但各分支单独绿？→ 可能两分支在**运行时**有隐性耦合（如都依赖某全局注册）。本批文件不相交、低概率；若出现，二分定位并在 main 上修。
