# 层级标定「动态挂载」(auto-nest) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the "动态挂载" semantics in 层级标定 mode — when a user promotes a leaf to a chapter, automatically reparent the following sibling leaves under the new chapter as a single transactional operation. Replace the broken per-row `convert-to-chapter` apply path with a new `POST /procedures/{id}/apply-layer-roles` endpoint.

**Architecture:** Backend gains a new `layer_apply_service` with its own walk (equivalent to frontend `computeLayerUpdates`) + transactional apply. Frontend `applyLayerRoles` collapses to a single API call, `validateLayerQ25` realigns to group by walk terminal state, and `LayerRow.originalParent` is removed. Double-walk equivalence is locked by a shared JSON fixture.

**Tech Stack:** FastAPI + SQLAlchemy (backend), Pinia + Vue 3 + Vitest (frontend), pytest. Optimistic lock via `If-Match` header (revision int).

**Reference spec:** `docs/superpowers/specs/2026-05-27-layer-overlay-auto-nest-design.md`

---

## Task 0: Baseline — confirm clean working tree and tests pass

**Files:** None (state check only)

- [ ] **Step 1: Verify spec exists + working tree clean except for unrelated parser changes**

Run:
```bash
git log --oneline -5
git status --short
```

Expected:
- Top commit is `a250fdb docs(specs): add layer-overlay auto-nest design`
- Status shows unrelated parser modifications (normalizer.py + its test) — these are not part of this plan; do not stage them.

- [ ] **Step 2: Run baseline backend tests for conversion_service + step_service**

Run:
```bash
backend/.venv/bin/python -m pytest backend/tests/unit/services/test_conversion_service.py backend/tests/unit/services/test_step_service.py -q
```

Expected: all pass. If failures, stop and investigate before proceeding — this plan assumes a green baseline.

- [ ] **Step 3: Run baseline frontend layerMark spec**

Run:
```bash
cd frontend && npm run test -- --run tests/unit/utils/layerMark.spec.ts
```

Expected: all pass.

---

## Task 1: Author shared walk fixture file

**Goal:** Lock the double-walk equivalence with a JSON fixture both frontends will consume.

**Files:**
- Create: `backend/tests/fixtures/layer_walk_fixtures.json`
- Create: `frontend/tests/fixtures/layerWalkFixtures.json` (identical content; manual copy — keep in sync by hand)

- [ ] **Step 1: Create fixture JSON**

Content (write to **both** paths identically):

```json
{
  "fixtures": [
    {
      "name": "single L1 chapter",
      "rows": [
        {"id":"A","kind":"chapter","level":1,"hasLeafChildren":false}
      ],
      "roles": {"A":"chapter_1"},
      "updates": {
        "A": {"kind":"reorder","parent_id":null,"sort_order":0,"level":1}
      }
    },
    {
      "name": "L1 + leaf keep → leaf-reparent under L1",
      "rows": [
        {"id":"A","kind":"chapter","level":1,"hasLeafChildren":true},
        {"id":"s1","kind":"step","level":0,"hasLeafChildren":false}
      ],
      "roles": {"A":"chapter_1"},
      "updates": {
        "A": {"kind":"reorder","parent_id":null,"sort_order":0,"level":1},
        "s1": {"kind":"leaf-reparent","parent_id":"A","sort_order":0}
      }
    },
    {
      "name": "L1 + leaf promoted to L2 + following leaf adopted",
      "rows": [
        {"id":"A","kind":"chapter","level":1,"hasLeafChildren":true},
        {"id":"c1","kind":"content","level":0,"hasLeafChildren":false},
        {"id":"d1","kind":"content","level":0,"hasLeafChildren":false}
      ],
      "roles": {"A":"chapter_1","c1":"chapter_2"},
      "updates": {
        "A": {"kind":"reorder","parent_id":null,"sort_order":0,"level":1},
        "c1": {"kind":"to-chapter","parent_id":"A","sort_order":0,"level":2},
        "d1": {"kind":"leaf-reparent","parent_id":"c1","sort_order":0}
      }
    },
    {
      "name": "screenshot scenario: three L2 promotions each adopt 2 leaves",
      "rows": [
        {"id":"R","kind":"chapter","level":1,"hasLeafChildren":true},
        {"id":"a","kind":"content","level":0,"hasLeafChildren":false},
        {"id":"a1","kind":"content","level":0,"hasLeafChildren":false},
        {"id":"a2","kind":"content","level":0,"hasLeafChildren":false},
        {"id":"b","kind":"content","level":0,"hasLeafChildren":false},
        {"id":"b1","kind":"content","level":0,"hasLeafChildren":false},
        {"id":"b2","kind":"content","level":0,"hasLeafChildren":false},
        {"id":"c","kind":"content","level":0,"hasLeafChildren":false},
        {"id":"c1","kind":"content","level":0,"hasLeafChildren":false},
        {"id":"c2","kind":"content","level":0,"hasLeafChildren":false}
      ],
      "roles": {"R":"chapter_1","a":"chapter_2","b":"chapter_2","c":"chapter_2"},
      "updates": {
        "R": {"kind":"reorder","parent_id":null,"sort_order":0,"level":1},
        "a": {"kind":"to-chapter","parent_id":"R","sort_order":0,"level":2},
        "a1": {"kind":"leaf-reparent","parent_id":"a","sort_order":0},
        "a2": {"kind":"leaf-reparent","parent_id":"a","sort_order":1},
        "b": {"kind":"to-chapter","parent_id":"R","sort_order":1,"level":2},
        "b1": {"kind":"leaf-reparent","parent_id":"b","sort_order":0},
        "b2": {"kind":"leaf-reparent","parent_id":"b","sort_order":1},
        "c": {"kind":"to-chapter","parent_id":"R","sort_order":2,"level":2},
        "c1": {"kind":"leaf-reparent","parent_id":"c","sort_order":0},
        "c2": {"kind":"leaf-reparent","parent_id":"c","sort_order":1}
      }
    },
    {
      "name": "L2 then L3 — L3 becomes child of L2, gets its own adoption block",
      "rows": [
        {"id":"R","kind":"chapter","level":1,"hasLeafChildren":true},
        {"id":"x","kind":"content","level":0,"hasLeafChildren":false},
        {"id":"x1","kind":"content","level":0,"hasLeafChildren":false},
        {"id":"y","kind":"content","level":0,"hasLeafChildren":false},
        {"id":"y1","kind":"content","level":0,"hasLeafChildren":false}
      ],
      "roles": {"R":"chapter_1","x":"chapter_2","y":"chapter_3"},
      "updates": {
        "R": {"kind":"reorder","parent_id":null,"sort_order":0,"level":1},
        "x": {"kind":"to-chapter","parent_id":"R","sort_order":0,"level":2},
        "x1": {"kind":"leaf-reparent","parent_id":"x","sort_order":0},
        "y": {"kind":"to-chapter","parent_id":"x","sort_order":0,"level":3},
        "y1": {"kind":"leaf-reparent","parent_id":"y","sort_order":0}
      }
    },
    {
      "name": "L3 without L2 context → clamped to L1",
      "rows": [
        {"id":"y","kind":"content","level":0,"hasLeafChildren":false}
      ],
      "roles": {"y":"chapter_3"},
      "updates": {
        "y": {"kind":"to-chapter","parent_id":null,"sort_order":0,"level":1}
      }
    },
    {
      "name": "chapter → content does not update heading context",
      "rows": [
        {"id":"A","kind":"chapter","level":1,"hasLeafChildren":false},
        {"id":"B","kind":"chapter","level":2,"hasLeafChildren":false},
        {"id":"s1","kind":"step","level":0,"hasLeafChildren":false}
      ],
      "roles": {"A":"chapter_1","B":"content"},
      "updates": {
        "A": {"kind":"reorder","parent_id":null,"sort_order":0,"level":1},
        "B": {"kind":"to-content","parent_id":"A","sort_order":0},
        "s1": {"kind":"leaf-reparent","parent_id":"A","sort_order":1}
      }
    },
    {
      "name": "empty roles map → leaves all keep, chapters all default",
      "rows": [
        {"id":"A","kind":"chapter","level":1,"hasLeafChildren":true},
        {"id":"s1","kind":"step","level":0,"hasLeafChildren":false}
      ],
      "roles": {},
      "updates": {
        "A": {"kind":"reorder","parent_id":null,"sort_order":0,"level":1},
        "s1": {"kind":"leaf-reparent","parent_id":"A","sort_order":0}
      }
    }
  ]
}
```

- [ ] **Step 2: Commit**

```bash
git add backend/tests/fixtures/layer_walk_fixtures.json frontend/tests/fixtures/layerWalkFixtures.json
git commit -m "$(cat <<'EOF'
test(layer-apply): add shared walk equivalence fixtures

Eight scenarios covering single chapter, leaf-reparent, L2 promotion +
adoption, screenshot scenario (3x L2), L2+L3 nested adoption, L3 clamp,
chapter→content not updating heading context, and empty roles. Both
backend and frontend will assert their walks produce these exact
LayerUpdate outputs.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Backend walk module — port computeLayerUpdates to Python

**Goal:** A pure function in Python that produces the same `LayerUpdate` dict as the frontend walk, driven by the shared fixture.

**Files:**
- Create: `backend/app/services/layer_walk.py`
- Create: `backend/tests/unit/services/test_layer_walk.py`

- [ ] **Step 1: Create the walk module skeleton**

`backend/app/services/layer_walk.py`:

```python
"""层级标定 walk(等价于 frontend `computeLayerUpdates`,见 layerMark.ts:59)。

输入:文档序的 LayerRow 列表 + role map。输出:每行的 LayerUpdate(tagged dict)。
双端等价性由 backend/tests/fixtures/layer_walk_fixtures.json 锁住。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

LayerRole = Literal["chapter_1", "chapter_2", "chapter_3", "content", "keep"]
RowKind = Literal["chapter", "step", "content"]


@dataclass(frozen=True)
class LayerRow:
    id: str
    kind: RowKind
    level: int
    has_leaf_children: bool


def default_layer_role(row: LayerRow) -> LayerRole:
    if row.kind != "chapter":
        return "keep"
    lv = min(3, max(1, row.level))
    return f"chapter_{lv}"  # type: ignore[return-value]


def _effective_role(row: LayerRow, role_map: dict[str, LayerRole]) -> LayerRole:
    role = role_map.get(row.id, default_layer_role(row))
    if row.kind == "chapter":
        if role == "content" and row.has_leaf_children:
            return default_layer_role(row)
        if role == "keep":
            return default_layer_role(row)
        return role
    if role == "content":
        return "keep"
    return role


def _role_level(role: LayerRole) -> int:
    return 3 if role == "chapter_3" else 2 if role == "chapter_2" else 1


def compute_layer_updates(
    rows: list[LayerRow], role_map: dict[str, LayerRole]
) -> dict[str, dict]:
    """对应 frontend computeLayerUpdates。返回 dict[id, LayerUpdate],其中 LayerUpdate 为:
        {"kind": "reorder",       "parent_id": str|None, "sort_order": int, "level": int}
      | {"kind": "to-content",    "parent_id": str|None, "sort_order": int}
      | {"kind": "to-chapter",    "parent_id": str|None, "sort_order": int, "level": int}
      | {"kind": "leaf-reparent", "parent_id": str|None, "sort_order": int}
    """
    out: dict[str, dict] = {}
    l1: str | None = None
    l2: str | None = None
    l3: str | None = None
    sort_counter: dict[str | None, int] = {}

    def next_sort(p: str | None) -> int:
        n = sort_counter.get(p, 0)
        sort_counter[p] = n + 1
        return n

    def place_chapter(requested: int) -> tuple[str | None, int]:
        if requested >= 3 and l2 is not None:
            return l2, 3
        if requested >= 2 and l1 is not None:
            return l1, 2
        return None, 1

    def set_heading(row_id: str, level: int) -> None:
        nonlocal l1, l2, l3
        if level == 1:
            l1, l2, l3 = row_id, None, None
        elif level == 2:
            l2, l3 = row_id, None
        else:
            l3 = row_id

    for row in rows:
        role = _effective_role(row, role_map)
        if row.kind == "chapter":
            if role == "content":
                parent = l3 or l2 or l1
                out[row.id] = {"kind": "to-content", "parent_id": parent, "sort_order": next_sort(parent)}
                continue
            requested = _role_level(role)
            parent, level = place_chapter(requested)
            set_heading(row.id, level)
            out[row.id] = {"kind": "reorder", "parent_id": parent, "sort_order": next_sort(parent), "level": level}
            continue
        if role == "keep":
            parent = l3 or l2 or l1
            out[row.id] = {"kind": "leaf-reparent", "parent_id": parent, "sort_order": next_sort(parent)}
            continue
        requested = _role_level(role)
        parent, level = place_chapter(requested)
        set_heading(row.id, level)
        out[row.id] = {"kind": "to-chapter", "parent_id": parent, "sort_order": next_sort(parent), "level": level}
    return out
```

- [ ] **Step 2: Write the fixture-driven test**

`backend/tests/unit/services/test_layer_walk.py`:

```python
"""layer_walk 单测——按 backend/tests/fixtures/layer_walk_fixtures.json 跑所有场景。
fixture 与 frontend/tests/fixtures/layerWalkFixtures.json 必须等价。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.layer_walk import LayerRow, compute_layer_updates

FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "layer_walk_fixtures.json"


def _load_fixtures() -> list[dict]:
    return json.loads(FIXTURE_PATH.read_text())["fixtures"]


@pytest.mark.parametrize("fx", _load_fixtures(), ids=lambda fx: fx["name"])
def test_walk_matches_fixture(fx: dict) -> None:
    rows = [
        LayerRow(
            id=r["id"],
            kind=r["kind"],
            level=r["level"],
            has_leaf_children=r["hasLeafChildren"],
        )
        for r in fx["rows"]
    ]
    role_map = fx["roles"]
    actual = compute_layer_updates(rows, role_map)
    assert actual == fx["updates"], (
        f"walk output mismatch for '{fx['name']}':\n"
        f"  expected: {fx['updates']}\n"
        f"  actual:   {actual}"
    )
```

- [ ] **Step 3: Run test to verify it passes (walk is already complete)**

Run:
```bash
backend/.venv/bin/python -m pytest backend/tests/unit/services/test_layer_walk.py -v
```

Expected: 8 passed (one per fixture).

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/layer_walk.py backend/tests/unit/services/test_layer_walk.py
git commit -m "$(cat <<'EOF'
feat(layer-apply): port computeLayerUpdates walk to Python

Pure-function walk producing LayerUpdate dicts identical to frontend
layerMark.ts:computeLayerUpdates. Equivalence enforced by shared
JSON fixture (8 scenarios incl. screenshot case + L2/L3 nesting).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Schemas — LayerApplyIn / LayerApplyOut / LayerConflictOut

**Files:**
- Modify: `backend/app/schemas/node.py` (append at end of file)

- [ ] **Step 1: Append schemas**

Add to the end of `backend/app/schemas/node.py`:

```python
class LayerApplyIn(BaseModel):
    """层级标定批量应用请求(spec §3.1)。
    roles 仅传需要明确角色的节点;未传节点视为 keep(叶子)/默认(章节)。
    """

    roles: dict[str, Literal["chapter_1", "chapter_2", "chapter_3", "content", "keep"]] = Field(
        default_factory=dict
    )


class LayerConflictOut(BaseModel):
    parent_id: str | None
    chapter_children: list[str]
    leaf_children: list[str]


class LayerApplyResult(BaseModel):
    """成功:返回本 batch leaf→new_chapter 映射 + 新 revision。"""

    chapter_map: dict[str, str] = Field(default_factory=dict)
    revision: int
```

Note: `Literal` needs `from typing import Literal` at the file top — check if it's already imported; if not, add it.

- [ ] **Step 2: Verify file still parses**

Run:
```bash
backend/.venv/bin/python -c "from app.schemas.node import LayerApplyIn, LayerApplyResult, LayerConflictOut; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/node.py
git commit -m "$(cat <<'EOF'
feat(layer-apply): add LayerApplyIn/Result/ConflictOut schemas

Pydantic models for POST /procedures/{id}/apply-layer-roles request +
response. ConflictOut carries §Q25 breakdown for the frontend banner.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Service skeleton + LayerRow rebuild from DB + Q25 validator + depth check

**Goal:** A service function that loads procedure, rebuilds LayerRow list from DB, runs walk, validates final state. No execution yet — just rejects bad inputs.

**Files:**
- Create: `backend/app/services/layer_apply_service.py`
- Create: `backend/tests/unit/services/test_layer_apply_service.py`

- [ ] **Step 1: Write the first failing test (Q25 conflict path)**

`backend/tests/unit/services/test_layer_apply_service.py`:

```python
"""layer_apply_service 单测(spec §5.1)。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.models.procedure import Procedure
from app.services import layer_apply_service
from tests.conftest import Factory

META = RequestMeta(ip_address="203.0.113.11", user_agent="pytest", request_id="r-la")


def _proc(factory: Factory) -> Procedure:
    leaf = factory.folder(name="叶子", prefix="QC", full_path="叶子")
    factory.sequence(leaf.id)
    return factory.procedure(leaf.id)


def test_q25_conflict_when_promoted_leaves_remaining_siblings(
    db: Session, factory: Factory
) -> None:
    """父 P 下两个 step 兄弟,只升一个 → 末态混合 → 400 SIBLING_TYPE_CONFLICT。"""
    proc = _proc(factory)
    ch = factory.chapter(proc.id, title="A", level=1)
    s1 = factory.step(proc.id, chapter_id=ch.id, kind="content", title="s1", sort_order=0)
    s2 = factory.step(proc.id, chapter_id=ch.id, kind="content", title="s2", sort_order=1)

    with pytest.raises(HTTPException) as ex:
        layer_apply_service.apply_layer_roles(
            db, proc.id, roles={s1.id: "chapter_2"}, expected_revision=proc.revision, meta=META
        )
    assert ex.value.status_code == 400
    assert ex.value.detail["code"] == "SIBLING_TYPE_CONFLICT"
    # DB 未变
    db.refresh(s1)
    db.refresh(s2)
    assert s1.is_active and s2.is_active
```

- [ ] **Step 2: Run test (should fail — service doesn't exist)**

Run:
```bash
backend/.venv/bin/python -m pytest backend/tests/unit/services/test_layer_apply_service.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.layer_apply_service'`

- [ ] **Step 3: Write the service skeleton (validators only, no execution)**

`backend/app/services/layer_apply_service.py`:

```python
"""层级标定批量应用 service(spec §3)。

事务性:加载 → walk → 校验 → Phase A → B → C → D → recompute + bump + audit。
任一阶段抛错 → router 层 db.rollback,DB 完全不变。

walk 与 frontend layerMark.ts:computeLayerUpdates 等价(见 layer_walk.py)。
"""

from __future__ import annotations

from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.errors import bad_request
from app.models.chapter import ProcedureChapter
from app.models.procedure import Procedure
from app.models.step import ProcedureStep
from app.services import optimistic_lock
from app.services.layer_walk import LayerRow, compute_layer_updates

LayerRole = Literal["chapter_1", "chapter_2", "chapter_3", "content", "keep"]
MAX_DEPTH = 3


def _get_proc_editable(db: Session, procedure_id: str) -> Procedure:
    proc = db.execute(
        select(Procedure).where(Procedure.id == procedure_id, Procedure.is_active.is_(True))
    ).scalar_one_or_none()
    if proc is None:
        raise bad_request("PROCEDURE_NOT_FOUND", "程序不存在")
    return proc


def _build_layer_rows(db: Session, procedure_id: str) -> list[LayerRow]:
    """从 DB 按文档序重建 LayerRow 列表(等价 frontend store.layerRows getter)。"""
    chapters = list(
        db.execute(
            select(ProcedureChapter).where(
                ProcedureChapter.procedure_id == procedure_id,
                ProcedureChapter.is_active.is_(True),
            )
        ).scalars()
    )
    steps = list(
        db.execute(
            select(ProcedureStep).where(
                ProcedureStep.procedure_id == procedure_id,
                ProcedureStep.is_active.is_(True),
            )
        ).scalars()
    )
    ch_by_parent: dict[str | None, list[ProcedureChapter]] = {}
    for c in chapters:
        ch_by_parent.setdefault(c.parent_id, []).append(c)
    st_by_chapter: dict[str | None, list[ProcedureStep]] = {}
    has_leaf: set[str | None] = set()
    for s in steps:
        st_by_chapter.setdefault(s.chapter_id, []).append(s)
        has_leaf.add(s.chapter_id)
    for lst in ch_by_parent.values():
        lst.sort(key=lambda c: (c.sort_order, c.id))
    for lst in st_by_chapter.values():
        lst.sort(key=lambda s: (s.sort_order, s.id))

    rows: list[LayerRow] = []

    def walk(parent: str | None) -> None:
        for c in ch_by_parent.get(parent, []):
            rows.append(
                LayerRow(
                    id=c.id,
                    kind="chapter",
                    level=c.level,
                    has_leaf_children=c.id in has_leaf,
                )
            )
            walk(c.id)
        for s in st_by_chapter.get(parent, []):
            rows.append(
                LayerRow(
                    id=s.id,
                    kind="content" if s.kind == "content" else "step",
                    level=0,
                    has_leaf_children=False,
                )
            )

    walk(None)
    return rows


def _validate_q25(updates: dict[str, dict]) -> None:
    """按 walk 末态 parent_id 分组——任一组同时含 chapter 类 + leaf 类 → SIBLING_TYPE_CONFLICT。"""
    groups: dict[str | None, dict[str, list[str]]] = {}
    chapter_kinds = {"reorder", "to-chapter"}
    leaf_kinds = {"to-content", "leaf-reparent"}
    for node_id, u in updates.items():
        g = groups.setdefault(u["parent_id"], {"chapters": [], "leaves": []})
        if u["kind"] in chapter_kinds:
            g["chapters"].append(node_id)
        elif u["kind"] in leaf_kinds:
            g["leaves"].append(node_id)
    conflicts = [
        {"parent_id": p, "chapter_children": sorted(g["chapters"]), "leaf_children": sorted(g["leaves"])}
        for p, g in groups.items()
        if g["chapters"] and g["leaves"]
    ]
    if conflicts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "SIBLING_TYPE_CONFLICT", "message": "末态同级混合", "conflicts": conflicts},
        )


def _validate_depth(updates: dict[str, dict]) -> None:
    for node_id, u in updates.items():
        if u["kind"] in ("reorder", "to-chapter") and u["level"] > MAX_DEPTH:
            raise bad_request("CHAPTER_DEPTH_EXCEEDED", f"章节嵌套超过 {MAX_DEPTH} 级")


def apply_layer_roles(
    db: Session,
    procedure_id: str,
    *,
    roles: dict[str, LayerRole],
    expected_revision: int,
    meta: RequestMeta,
) -> dict:
    proc = _get_proc_editable(db, procedure_id)
    optimistic_lock.verify_revision(proc.revision, expected_revision)
    rows = _build_layer_rows(db, procedure_id)
    updates = compute_layer_updates(rows, roles)
    _validate_q25(updates)
    _validate_depth(updates)
    # Execution phases A-D come in subsequent tasks.
    return {"chapter_map": {}, "revision": proc.revision}
```

- [ ] **Step 4: Run test to verify it now passes**

Run:
```bash
backend/.venv/bin/python -m pytest backend/tests/unit/services/test_layer_apply_service.py::test_q25_conflict_when_promoted_leaves_remaining_siblings -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/layer_apply_service.py backend/tests/unit/services/test_layer_apply_service.py
git commit -m "$(cat <<'EOF'
feat(layer-apply): scaffold service + Q25 / depth validators

apply_layer_roles loads procedure, verifies revision, rebuilds LayerRow
list from DB, runs walk, validates final state via §Q25 mutual exclusion
+ depth ≤3. Execution phases follow in next commits.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Phase A — to-chapter execution + leaf→new_chapter map

**Files:**
- Modify: `backend/app/services/layer_apply_service.py`
- Modify: `backend/tests/unit/services/test_layer_apply_service.py` (add tests)

- [ ] **Step 1: Add failing test for single-leaf promotion (happy path)**

Append to `test_layer_apply_service.py`:

```python
def test_phase_a_single_leaf_promoted_no_siblings(db: Session, factory: Factory) -> None:
    """父 P 下唯一 leaf 升 L2 → 创建新 L2 chapter,原 leaf 软删,body 转 child content。"""
    proc = _proc(factory)
    ch = factory.chapter(proc.id, title="A", level=1)
    s1 = factory.step(
        proc.id, chapter_id=ch.id, kind="content", title="崔宇明", content="<p>负责...</p>", sort_order=0
    )

    result = layer_apply_service.apply_layer_roles(
        db, proc.id, roles={s1.id: "chapter_2"}, expected_revision=proc.revision, meta=META
    )

    # 新章节存在
    assert len(result["chapter_map"]) == 1
    new_ch_id = result["chapter_map"][s1.id]
    db.refresh(s1)
    assert not s1.is_active  # 原 leaf 软删
    new_ch = db.get(__import__("app.models.chapter", fromlist=["ProcedureChapter"]).ProcedureChapter, new_ch_id)
    assert new_ch is not None
    assert new_ch.title == "崔宇明"
    assert new_ch.parent_id == ch.id
    assert new_ch.level == 2
    # body 转为子 content step
    from app.models.step import ProcedureStep
    children = db.execute(
        select(ProcedureStep).where(ProcedureStep.chapter_id == new_ch_id, ProcedureStep.is_active.is_(True))
    ).scalars().all()
    assert len(children) == 1
    assert children[0].kind == "content"
    assert children[0].content == "<p>负责...</p>"
```

- [ ] **Step 2: Run test (should fail — Phase A not implemented)**

Run:
```bash
backend/.venv/bin/python -m pytest backend/tests/unit/services/test_layer_apply_service.py::test_phase_a_single_leaf_promoted_no_siblings -v
```

Expected: FAIL (assertion on `chapter_map` length).

- [ ] **Step 3: Implement Phase A in service**

Add to `layer_apply_service.py` (replace the placeholder return in `apply_layer_roles`):

```python
def _phase_a_to_chapter(
    db: Session,
    proc: Procedure,
    rows: list[LayerRow],
    updates: dict[str, dict],
) -> dict[str, str]:
    """按文档序执行 to-chapter。返回 leaf_id → new_chapter_id 映射。
    parent_id 解析:若 walk 给的 parent 命中映射(同 batch 先一步升的叶子),
    则替换为对应新 chapter id;否则原样使用(指向现存 chapter 或 null)。"""
    chapter_map: dict[str, str] = {}
    row_by_id = {r.id: r for r in rows}
    step_by_id = {
        s.id: s for s in db.execute(
            select(ProcedureStep).where(
                ProcedureStep.procedure_id == proc.id,
                ProcedureStep.is_active.is_(True),
            )
        ).scalars()
    }
    from app.models.base import utcnow
    for row in rows:  # 文档序遍历,保证 map 在被引用前已填充
        u = updates.get(row.id)
        if not u or u["kind"] != "to-chapter":
            continue
        st = step_by_id[row.id]
        resolved_parent = chapter_map.get(u["parent_id"], u["parent_id"])
        new_ch = ProcedureChapter(
            procedure_id=proc.id,
            parent_id=resolved_parent,
            title=st.title or "未命名章节",
            sort_order=u["sort_order"],
            level=u["level"],
        )
        db.add(new_ch)
        db.flush()
        if st.content and st.content.strip():
            child = ProcedureStep(
                procedure_id=proc.id,
                chapter_id=new_ch.id,
                kind="content",
                title="",
                content=st.content,
                input_schema={},
                sort_order=0,
            )
            db.add(child)
            db.flush()
        st.is_active = False
        st.deleted_at = utcnow()
        chapter_map[row.id] = new_ch.id
    return chapter_map
```

And update `apply_layer_roles` body:

```python
def apply_layer_roles(
    db: Session,
    procedure_id: str,
    *,
    roles: dict[str, LayerRole],
    expected_revision: int,
    meta: RequestMeta,
) -> dict:
    proc = _get_proc_editable(db, procedure_id)
    optimistic_lock.verify_revision(proc.revision, expected_revision)
    rows = _build_layer_rows(db, procedure_id)
    updates = compute_layer_updates(rows, roles)
    _validate_q25(updates)
    _validate_depth(updates)

    chapter_map = _phase_a_to_chapter(db, proc, rows, updates)
    # Phase B / C / D + finalize come next.
    db.flush()
    return {"chapter_map": chapter_map, "revision": proc.revision}
```

- [ ] **Step 4: Run Phase A test**

Run:
```bash
backend/.venv/bin/python -m pytest backend/tests/unit/services/test_layer_apply_service.py::test_phase_a_single_leaf_promoted_no_siblings -v
```

Expected: PASS.

- [ ] **Step 5: Re-run Q25 test to confirm no regression**

Run:
```bash
backend/.venv/bin/python -m pytest backend/tests/unit/services/test_layer_apply_service.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/layer_apply_service.py backend/tests/unit/services/test_layer_apply_service.py
git commit -m "$(cat <<'EOF'
feat(layer-apply): Phase A — to-chapter execution

Per-row promotion in document order, building leaf_id→new_chapter_id
map so subsequent rows' walk parent_ids resolve correctly. Preserves
convert_to_chapter semantics: title or "未命名章节", body becomes
child content step if non-empty, original leaf soft-deleted.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Phase B (reorder) + Phase C (to-content with CHAPTER_HAS_CHILDREN)

**Files:**
- Modify: `backend/app/services/layer_apply_service.py`
- Modify: `backend/tests/unit/services/test_layer_apply_service.py`

- [ ] **Step 1: Add failing test for chapter reorder + chapter→content**

Append to `test_layer_apply_service.py`:

```python
def test_phase_bc_reorder_and_to_content(db: Session, factory: Factory) -> None:
    """A(L1) + B(L1) 调整为 A(L1) + B(content under A)。"""
    proc = _proc(factory)
    a = factory.chapter(proc.id, title="A", level=1, sort_order=0)
    b = factory.chapter(proc.id, title="B", level=1, sort_order=1)

    layer_apply_service.apply_layer_roles(
        db,
        proc.id,
        roles={a.id: "chapter_1", b.id: "content"},
        expected_revision=proc.revision,
        meta=META,
    )

    db.refresh(a)
    db.refresh(b)
    assert a.is_active and a.parent_id is None and a.level == 1
    assert not b.is_active  # chapter B 被软删
    # A 下有一个 content step,title 为空,body = "<p>B</p>"
    from app.models.step import ProcedureStep
    children = db.execute(
        select(ProcedureStep).where(ProcedureStep.chapter_id == a.id, ProcedureStep.is_active.is_(True))
    ).scalars().all()
    assert len(children) == 1
    assert children[0].kind == "content"
    assert children[0].content == "<p>B</p>"


def test_phase_c_chapter_has_children_rejects(db: Session, factory: Factory) -> None:
    """有子 chapter 的章节不可降为 content → 400 CHAPTER_HAS_CHILDREN。"""
    proc = _proc(factory)
    a = factory.chapter(proc.id, title="A", level=1, sort_order=0)
    factory.chapter(proc.id, title="A.1", parent_id=a.id, level=2, sort_order=0)

    with pytest.raises(HTTPException) as ex:
        layer_apply_service.apply_layer_roles(
            db,
            proc.id,
            roles={a.id: "content"},
            expected_revision=proc.revision,
            meta=META,
        )
    assert ex.value.status_code == 400
    assert ex.value.detail["code"] == "CHAPTER_HAS_CHILDREN"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
backend/.venv/bin/python -m pytest backend/tests/unit/services/test_layer_apply_service.py::test_phase_bc_reorder_and_to_content backend/tests/unit/services/test_layer_apply_service.py::test_phase_c_chapter_has_children_rejects -v
```

Expected: FAIL.

- [ ] **Step 3: Implement Phase B + Phase C**

Add to `layer_apply_service.py`:

```python
import html as _html


def _has_chapter_children(db: Session, proc_id: str, chapter_id: str) -> bool:
    return db.execute(
        select(ProcedureChapter.id).where(
            ProcedureChapter.procedure_id == proc_id,
            ProcedureChapter.parent_id == chapter_id,
            ProcedureChapter.is_active.is_(True),
        )
    ).first() is not None


def _phase_b_reorder(
    db: Session, updates: dict[str, dict], chapter_map: dict[str, str]
) -> None:
    """章节重排 / 调级 (in-place UPDATE)。"""
    for node_id, u in updates.items():
        if u["kind"] != "reorder":
            continue
        ch = db.get(ProcedureChapter, node_id)
        if ch is None or not ch.is_active:
            continue
        ch.parent_id = chapter_map.get(u["parent_id"], u["parent_id"])
        ch.sort_order = u["sort_order"]
        ch.level = u["level"]


def _phase_c_to_content(
    db: Session,
    proc: Procedure,
    updates: dict[str, dict],
    chapter_map: dict[str, str],
) -> None:
    """章节降为 content step。校验 CHAPTER_HAS_CHILDREN(后端兜底)。"""
    from app.models.base import utcnow
    for node_id, u in updates.items():
        if u["kind"] != "to-content":
            continue
        ch = db.get(ProcedureChapter, node_id)
        if ch is None or not ch.is_active:
            continue
        if _has_chapter_children(db, proc.id, ch.id):
            raise bad_request("CHAPTER_HAS_CHILDREN", f"章节 {ch.title or ch.id} 仍含子章节,不可降为内容")
        title = ch.title or ""
        body = f"<p>{_html.escape(title)}</p>" if title.strip() else ""
        new_step = ProcedureStep(
            procedure_id=proc.id,
            chapter_id=chapter_map.get(u["parent_id"], u["parent_id"]),
            kind="content",
            title="",
            content=body,
            input_schema={},
            sort_order=u["sort_order"],
        )
        db.add(new_step)
        db.flush()
        ch.is_active = False
        ch.deleted_at = utcnow()
```

Wire into `apply_layer_roles`:

```python
    chapter_map = _phase_a_to_chapter(db, proc, rows, updates)
    _phase_b_reorder(db, updates, chapter_map)
    _phase_c_to_content(db, proc, updates, chapter_map)
    db.flush()
    return {"chapter_map": chapter_map, "revision": proc.revision}
```

- [ ] **Step 4: Run all service tests**

Run:
```bash
backend/.venv/bin/python -m pytest backend/tests/unit/services/test_layer_apply_service.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/layer_apply_service.py backend/tests/unit/services/test_layer_apply_service.py
git commit -m "$(cat <<'EOF'
feat(layer-apply): Phase B (reorder) + Phase C (to-content)

Phase B: chapter reorder/relevel via in-place UPDATE, parent_id
resolved through Phase A map. Phase C: chapter→content creates new
kind='content' step with <p>title</p> body, soft-deletes chapter,
rejects with CHAPTER_HAS_CHILDREN if any active child chapter remains.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Phase D (leaf-reparent) + finalize (numbering + bump + audit)

**Files:**
- Modify: `backend/app/services/layer_apply_service.py`
- Modify: `backend/tests/unit/services/test_layer_apply_service.py`

- [ ] **Step 1: Add failing test for screenshot scenario (3.1/3.2/3.3 promotion + adoption)**

Append to `test_layer_apply_service.py`:

```python
def test_screenshot_scenario_three_l2_promotions_with_adoption(
    db: Session, factory: Factory
) -> None:
    """截图场景:3.0 下三组(姓名 + 2 描述),三个姓名升 L2,各吃 2 个描述。"""
    proc = _proc(factory)
    r = factory.chapter(proc.id, title="职责", level=1, sort_order=0)
    a = factory.step(proc.id, chapter_id=r.id, kind="content", title="崔宇明", sort_order=0)
    a1 = factory.step(proc.id, chapter_id=r.id, kind="content", content="<p>负责编制本程序</p>", sort_order=1)
    a2 = factory.step(proc.id, chapter_id=r.id, kind="content", content="<p>全面负责财务</p>", sort_order=2)
    b = factory.step(proc.id, chapter_id=r.id, kind="content", title="王覆宇", sort_order=3)
    b1 = factory.step(proc.id, chapter_id=r.id, kind="content", content="<p>架构设计</p>", sort_order=4)
    b2 = factory.step(proc.id, chapter_id=r.id, kind="content", content="<p>服务器部署</p>", sort_order=5)
    c = factory.step(proc.id, chapter_id=r.id, kind="content", title="于星河", sort_order=6)
    c1 = factory.step(proc.id, chapter_id=r.id, kind="content", content="<p>前端开发</p>", sort_order=7)
    c2 = factory.step(proc.id, chapter_id=r.id, kind="content", content="<p>开发流程</p>", sort_order=8)

    result = layer_apply_service.apply_layer_roles(
        db,
        proc.id,
        roles={a.id: "chapter_2", b.id: "chapter_2", c.id: "chapter_2"},
        expected_revision=proc.revision,
        meta=META,
    )

    new_a, new_b, new_c = result["chapter_map"][a.id], result["chapter_map"][b.id], result["chapter_map"][c.id]
    from app.models.chapter import ProcedureChapter as Ch
    for nid, expected_title in [(new_a, "崔宇明"), (new_b, "王覆宇"), (new_c, "于星河")]:
        ch = db.get(Ch, nid)
        assert ch is not None and ch.parent_id == r.id and ch.level == 2 and ch.title == expected_title
    # 三个描述对应挂在三个新章节下
    db.refresh(a1); db.refresh(a2); db.refresh(b1); db.refresh(b2); db.refresh(c1); db.refresh(c2)
    assert a1.chapter_id == new_a and a2.chapter_id == new_a
    assert b1.chapter_id == new_b and b2.chapter_id == new_b
    assert c1.chapter_id == new_c and c2.chapter_id == new_c
    # 描述行的 sort_order 应该是 0, 1(在各自新章节下)
    assert sorted([a1.sort_order, a2.sort_order]) == [0, 1]
```

- [ ] **Step 2: Run test (should fail — leaf-reparent not implemented yet)**

Run:
```bash
backend/.venv/bin/python -m pytest backend/tests/unit/services/test_layer_apply_service.py::test_screenshot_scenario_three_l2_promotions_with_adoption -v
```

Expected: FAIL (a1.chapter_id == new_a fails — still pointing to r.id).

- [ ] **Step 3: Implement Phase D + finalize**

Add to `layer_apply_service.py`:

```python
from app.services import numbering_service


def _phase_d_leaf_reparent(
    db: Session, updates: dict[str, dict], chapter_map: dict[str, str]
) -> None:
    """叶子重挂(保持角色叶子)。已被 Phase A 软删的叶子跳过。"""
    for node_id, u in updates.items():
        if u["kind"] != "leaf-reparent":
            continue
        st = db.get(ProcedureStep, node_id)
        if st is None or not st.is_active:
            continue
        st.chapter_id = chapter_map.get(u["parent_id"], u["parent_id"])
        st.sort_order = u["sort_order"]
```

Update `apply_layer_roles` to add Phase D + finalize:

```python
    chapter_map = _phase_a_to_chapter(db, proc, rows, updates)
    _phase_b_reorder(db, updates, chapter_map)
    _phase_c_to_content(db, proc, updates, chapter_map)
    _phase_d_leaf_reparent(db, updates, chapter_map)
    db.flush()
    numbering_service.recompute(db, proc.id)
    optimistic_lock.bump(proc)
    db.flush()
    return {"chapter_map": chapter_map, "revision": proc.revision}
```

- [ ] **Step 4: Add audit logging**

`conversion_service.py:225` defines a local `_audit` helper that wraps `audit_service.log_procedure_action`. Replicate the same call inline in `layer_apply_service.py`.

Add to imports at top of `layer_apply_service.py`:

```python
from app.services import audit_service
```

And after `optimistic_lock.bump(proc)` in `apply_layer_roles`:

```python
    audit_service.log_procedure_action(
        db,
        target_id=proc.id,
        procedure_group_id=proc.procedure_group_id,
        action="apply-layer-roles",
        meta=meta,
        old_value={"role_count": len(roles)},
        new_value={"chapter_map": chapter_map},
    )
```

- [ ] **Step 5: Run all service tests**

Run:
```bash
backend/.venv/bin/python -m pytest backend/tests/unit/services/test_layer_apply_service.py -v
```

Expected: 5 passed (incl. screenshot scenario).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/layer_apply_service.py backend/tests/unit/services/test_layer_apply_service.py
git commit -m "$(cat <<'EOF'
feat(layer-apply): Phase D (leaf-reparent) + finalize

Phase D moves keep-role leaves under their walk-target parent (resolved
via Phase A map for newly-promoted-leaf targets). Finalize: recompute
numbering, bump optimistic lock, write apply-layer-roles audit.

Screenshot scenario (3.1/3.2/3.3 each adopting 2 description leaves)
now passes end-to-end.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Service tests — remaining spec §5 cases

**Files:**
- Modify: `backend/tests/unit/services/test_layer_apply_service.py`

- [ ] **Step 1: Add the remaining service-level cases**

Append to `test_layer_apply_service.py`:

```python
def test_l3_clamped_to_l1_when_no_l2_context(db: Session, factory: Factory) -> None:
    """根级叶子标 L3 → walk 夹到 L1。"""
    proc = _proc(factory)
    s = factory.step(proc.id, chapter_id=None, kind="content", title="孤行", sort_order=0)
    result = layer_apply_service.apply_layer_roles(
        db, proc.id, roles={s.id: "chapter_3"}, expected_revision=proc.revision, meta=META
    )
    from app.models.chapter import ProcedureChapter as Ch
    new_ch = db.get(Ch, result["chapter_map"][s.id])
    assert new_ch.parent_id is None
    assert new_ch.level == 1


def test_l2_then_l3_nested_adoption(db: Session, factory: Factory) -> None:
    """L2 + L3,L3 成为 L2 的子章节,L3 的收养块在 L3 下。"""
    proc = _proc(factory)
    r = factory.chapter(proc.id, title="R", level=1)
    x = factory.step(proc.id, chapter_id=r.id, kind="content", title="X", sort_order=0)
    x1 = factory.step(proc.id, chapter_id=r.id, kind="content", content="<p>x1</p>", sort_order=1)
    y = factory.step(proc.id, chapter_id=r.id, kind="content", title="Y", sort_order=2)
    y1 = factory.step(proc.id, chapter_id=r.id, kind="content", content="<p>y1</p>", sort_order=3)

    result = layer_apply_service.apply_layer_roles(
        db,
        proc.id,
        roles={x.id: "chapter_2", y.id: "chapter_3"},
        expected_revision=proc.revision,
        meta=META,
    )
    new_x, new_y = result["chapter_map"][x.id], result["chapter_map"][y.id]
    from app.models.chapter import ProcedureChapter as Ch
    assert db.get(Ch, new_x).parent_id == r.id and db.get(Ch, new_x).level == 2
    assert db.get(Ch, new_y).parent_id == new_x and db.get(Ch, new_y).level == 3
    db.refresh(x1); db.refresh(y1)
    assert x1.chapter_id == new_x
    assert y1.chapter_id == new_y


def test_depth_validator_rejects_level_4() -> None:
    """Walk 总是夹紧到 ≤3,所以 depth 校验是 defense-in-depth,直接构造 updates 测试。"""
    fake_updates = {
        "x": {"kind": "to-chapter", "parent_id": "y", "sort_order": 0, "level": 4}
    }
    with pytest.raises(HTTPException) as ex:
        layer_apply_service._validate_depth(fake_updates)
    assert ex.value.detail["code"] == "CHAPTER_DEPTH_EXCEEDED"


def test_optimistic_lock_conflict(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    with pytest.raises(HTTPException) as ex:
        layer_apply_service.apply_layer_roles(
            db, proc.id, roles={}, expected_revision=proc.revision + 1, meta=META
        )
    assert ex.value.status_code == 409


def test_empty_roles_noop(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    ch = factory.chapter(proc.id, title="A", level=1)
    factory.step(proc.id, chapter_id=ch.id, kind="content", title="x", sort_order=0)
    before_revision = proc.revision
    result = layer_apply_service.apply_layer_roles(
        db, proc.id, roles={}, expected_revision=before_revision, meta=META
    )
    # 即使是 noop,revision 也会被 bump(简单起见,不为 noop 特判);可接受。
    assert result["chapter_map"] == {}


def test_to_content_empty_title_produces_empty_body(db: Session, factory: Factory) -> None:
    proc = _proc(factory)
    a = factory.chapter(proc.id, title="A", level=1, sort_order=0)
    b = factory.chapter(proc.id, title="", level=1, sort_order=1)  # 空标题章节
    layer_apply_service.apply_layer_roles(
        db, proc.id, roles={a.id: "chapter_1", b.id: "content"}, expected_revision=proc.revision, meta=META
    )
    from app.models.step import ProcedureStep
    children = db.execute(
        select(ProcedureStep).where(ProcedureStep.chapter_id == a.id, ProcedureStep.is_active.is_(True))
    ).scalars().all()
    assert len(children) == 1
    assert children[0].content == ""  # 不是 "<p></p>"
```

- [ ] **Step 2: Run all service tests**

Run:
```bash
backend/.venv/bin/python -m pytest backend/tests/unit/services/test_layer_apply_service.py -v
```

Expected: 11 passed. If `test_depth_exceeded_rolls_back` fails, inspect walk output for the L3-under-L3 case and adjust the test setup or assertion to match actual walk behavior (the walk may dispatch to L3 max via clamp).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/services/test_layer_apply_service.py
git commit -m "$(cat <<'EOF'
test(layer-apply): cover L3 clamp, nested adoption, depth, lock, noop, empty-title to-content

Spec §5 cases 5/10/11/13/14 + optimistic-lock 409.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Backend router — POST /procedures/{id}/apply-layer-roles

**Files:**
- Modify: `backend/app/routers/procedures.py`

- [ ] **Step 1: Add imports for the new schema + service**

Locate the imports block in `procedures.py` (around line 15-30) and add to `from app.schemas.node import ApplyMarksResult` line:

```python
from app.schemas.node import ApplyMarksResult, LayerApplyIn, LayerApplyResult
```

And in the services imports section:

```python
from app.services import (
    # ... existing imports
    layer_apply_service,
)
```

- [ ] **Step 2: Register the route**

Add near the `apply_marks` endpoint (`procedures.py:260-268`):

```python
@router.post("/{procedure_id}/apply-layer-roles", response_model=LayerApplyResult)
def apply_layer_roles(
    procedure_id: str,
    payload: LayerApplyIn,
    db: Session = Depends(get_db),
    meta: RequestMeta = Depends(get_request_meta),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> LayerApplyResult:
    """层级标定批量应用(spec)。事务性:walk → 校验 → Phase A-D → recompute + bump + audit。"""
    expected = ensure_if_match(if_match)
    result = layer_apply_service.apply_layer_roles(
        db, procedure_id, roles=payload.roles, expected_revision=expected, meta=meta
    )
    db.commit()
    return LayerApplyResult(**result)
```

Find `ensure_if_match` import — likely already imported via `from app.services.optimistic_lock import ensure_if_match` or similar. If not, add it.

- [ ] **Step 3: Add a router smoke test**

Append to `backend/tests/unit/services/test_layer_apply_service.py` (or create `backend/tests/integration/test_procedures_apply_layer.py` if your test layout has integration dir):

```python
def test_router_smoke(client, factory: Factory) -> None:
    """通过 FastAPI TestClient 端到端跑一次 happy path,验证 If-Match + JSON body。"""
    leaf = factory.folder(name="叶子", prefix="QC", full_path="叶子")
    factory.sequence(leaf.id)
    proc = factory.procedure(leaf.id)
    ch = factory.chapter(proc.id, title="A", level=1)
    s = factory.step(proc.id, chapter_id=ch.id, kind="content", title="X", sort_order=0)

    resp = client.post(
        f"/api/v1/procedures/{proc.id}/apply-layer-roles",
        json={"roles": {s.id: "chapter_2"}},
        headers={"If-Match": str(proc.revision)},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert s.id in body["chapter_map"]
    assert body["revision"] > proc.revision
```

The `client` fixture is defined in `backend/tests/conftest.py:58` (`TestClient(app)` with `get_db` overridden to test engine). Inject it as a test parameter alongside `factory` — pytest will resolve both fixtures.

- [ ] **Step 4: Run router test**

Run:
```bash
backend/.venv/bin/python -m pytest backend/tests/unit/services/test_layer_apply_service.py::test_router_smoke -v
```

Expected: PASS. If the test client fixture isn't available in this file, put the test in an integration test file where it is.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/procedures.py backend/tests/unit/services/test_layer_apply_service.py
git commit -m "$(cat <<'EOF'
feat(layer-apply): wire POST /procedures/{id}/apply-layer-roles router

If-Match header → expected_revision; body = roles map. Smoke test
covers happy path through TestClient.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Frontend — realign validateLayerQ25 + drop LayerRow.originalParent

**Files:**
- Modify: `frontend/src/utils/layerMark.ts`
- Modify: `frontend/tests/unit/utils/layerMark.spec.ts`
- Modify: `frontend/src/store/procedureEditor.ts` (layerRows getter, lines 232-273)

- [ ] **Step 1: Update layerMark.ts — remove originalParent + realign validator**

In `frontend/src/utils/layerMark.ts`:

Replace `LayerRow` interface (line 4-12):

```typescript
/** 文档序里参与层级标定的行——含章节与叶子（step / content）。 */
export interface LayerRow {
  id: string
  kind: 'chapter' | 'step' | 'content'
  level: number // chapter 当前层级（叶子行 level=0 占位）
  hasLeafChildren: boolean // 仅 chapter 有意义：挂了步骤/内容块 → 不可降为 content
}
```

Replace `validateLayerQ25` function (line 144-187):

```typescript
/**
 * Dry-run §Q25 同级互斥校验。
 *
 * 与后端 layer_apply_service 等价:按 walk 末态 (u.parent_id) 分组。
 * 后端 apply-layer-roles 端点执行同一份 walk 后会落到完全相同的拓扑,
 * 因此前端 dry-run 不会假阳性 / 假阴性。
 */
export function validateLayerQ25(
  rows: LayerRow[],
  updates: Map<string, LayerUpdate>,
): LayerConflict[] {
  // 算每行的 (endKind, endParent) — apply 完成后的真实归属。
  type End = { kind: 'chapter' | 'leaf'; parent: string | null }
  const endOf = new Map<string, End>()
  for (const [id, u] of updates) {
    switch (u.kind) {
      case 'reorder':       endOf.set(id, { kind: 'chapter', parent: u.parent_id }); break
      case 'to-content':    endOf.set(id, { kind: 'leaf',    parent: u.parent_id }); break
      case 'to-chapter':    endOf.set(id, { kind: 'chapter', parent: u.parent_id }); break
      case 'leaf-reparent': endOf.set(id, { kind: 'leaf',    parent: u.parent_id }); break
    }
  }
  const groups = new Map<string | null, { chapters: string[]; leaves: string[] }>()
  for (const [id, end] of endOf) {
    const g = groups.get(end.parent) ?? { chapters: [], leaves: [] }
    if (end.kind === 'chapter') g.chapters.push(id)
    else g.leaves.push(id)
    groups.set(end.parent, g)
  }
  const conflicts: LayerConflict[] = []
  for (const [parent_id, g] of groups) {
    if (g.chapters.length > 0 && g.leaves.length > 0) {
      conflicts.push({ parent_id, chapterChildren: g.chapters, leafChildren: g.leaves })
    }
  }
  return conflicts
}
```

- [ ] **Step 2: Update store.layerRows — drop originalParent population**

In `frontend/src/store/procedureEditor.ts:252-258`, remove the `originalParent: c.parent_id` field:

```typescript
          rows.push({
            id: c.id,
            kind: 'chapter',
            level: levels.get(c.id) ?? 1,
            hasLeafChildren: hasStep.has(c.id),
          })
```

And line 262-268, remove `originalParent: s.chapter_id`:

```typescript
          rows.push({
            id: s.id,
            kind: s.kind === 'content' ? 'content' : 'step',
            level: 0,
            hasLeafChildren: false,
          })
```

- [ ] **Step 3: Update layerMark.spec.ts to match new semantics**

Replace the `row()` helper (line 11-19):

```typescript
function row(
  id: string,
  kind: 'chapter' | 'step' | 'content',
  level: number,
  hasLeafChildren = false,
): LayerRow {
  return { id, kind, level, hasLeafChildren }
}
```

Then remove every `originalParent: ...` field from existing test rows — use a regex find/replace. Run:

```bash
cd frontend && sed -i.bak 's/, *originalParent: [^,}]*//g; s/originalParent: [^,}]*, *//g' tests/unit/utils/layerMark.spec.ts
rm tests/unit/utils/layerMark.spec.ts.bak
```

Then replace the **`validateLayerQ25` describe block** (lines ~136-198) with new semantics:

```typescript
describe('validateLayerQ25', () => {
  it('提升一个叶子,父下另一叶子被 walk 挂到新章节下 → 无冲突', () => {
    // s1, s2 都在 A 下,s1 升 L2,walk 算 s2.parent=s1(末态正确)
    const rows: LayerRow[] = [
      { id: 'A', kind: 'chapter', level: 1, hasLeafChildren: true },
      { id: 's1', kind: 'step', level: 0, hasLeafChildren: false },
      { id: 's2', kind: 'step', level: 0, hasLeafChildren: false },
    ]
    const updates = computeLayerUpdates(rows, new Map([
      ['A', 'chapter_1'],
      ['s1', 'chapter_2'],
    ]))
    expect(validateLayerQ25(rows, updates)).toEqual([])
  })

  it('父下有 chapter 兄弟,再混入未被升的叶子且不属于任何收养块 → 冲突', () => {
    // A(L1) + B(L1, sibling) + s1(leaf under A) keep:
    // walk: A reorder@null, B reorder@null(变成 A 的 sibling), s1 leaf-reparent@A
    // 父 null 下 [A, B](chapters),父 A 下 [s1](leaf) — 无冲突。
    // 但如果加一个根级 leaf:
    const rows: LayerRow[] = [
      { id: 'A', kind: 'chapter', level: 1, hasLeafChildren: true },
      { id: 's1', kind: 'step', level: 0, hasLeafChildren: false },
      { id: 'orphan', kind: 'content', level: 0, hasLeafChildren: false },
    ]
    // s1 升 L2 → walk: A reorder@null L1, s1 to-chapter@A L2, orphan leaf-reparent@s1
    // 末态:null 下 A(chapter),A 下 s1(chapter),s1 下 orphan(leaf) — 无冲突。
    // 改造:在 s1 之前先加一个 leaf 兄弟保持 keep,它走 leaf-reparent@A,与 s1(chapter@A) 同 parent:
    const rows2: LayerRow[] = [
      { id: 'A', kind: 'chapter', level: 1, hasLeafChildren: true },
      { id: 'k', kind: 'content', level: 0, hasLeafChildren: false },
      { id: 's1', kind: 'step', level: 0, hasLeafChildren: false },
    ]
    const updates2 = computeLayerUpdates(rows2, new Map([
      ['A', 'chapter_1'],
      ['s1', 'chapter_2'],
    ]))
    const conflicts = validateLayerQ25(rows2, updates2)
    // walk 算:k 在 s1 之前,leaf-reparent@A;s1 to-chapter@A。
    // A 下:[k(leaf), s1(chapter)] → 冲突
    expect(conflicts).toHaveLength(1)
    expect(conflicts[0].parent_id).toBe('A')
    expect(conflicts[0].chapterChildren).toEqual(['s1'])
    expect(conflicts[0].leafChildren).toEqual(['k'])
  })

  it('全 leaf 兄弟(无章节兄弟) → 无冲突', () => {
    const rows: LayerRow[] = [
      { id: 'A', kind: 'chapter', level: 1, hasLeafChildren: true },
      { id: 's1', kind: 'step', level: 0, hasLeafChildren: false },
      { id: 's2', kind: 'step', level: 0, hasLeafChildren: false },
    ]
    const updates = computeLayerUpdates(rows, new Map([['A', 'chapter_1']]))
    expect(validateLayerQ25(rows, updates)).toEqual([])
  })

  it('父下唯一 step 提升 → 无冲突', () => {
    const rows: LayerRow[] = [
      { id: 'A', kind: 'chapter', level: 1, hasLeafChildren: true },
      { id: 's1', kind: 'step', level: 0, hasLeafChildren: false },
    ]
    const updates = computeLayerUpdates(rows, new Map([
      ['A', 'chapter_1'],
      ['s1', 'chapter_2'],
    ]))
    expect(validateLayerQ25(rows, updates)).toEqual([])
  })
})
```

- [ ] **Step 4: Add fixture-driven walk equivalence test**

Append to `frontend/tests/unit/utils/layerMark.spec.ts`:

```typescript
import fixtures from '../../fixtures/layerWalkFixtures.json'

describe('computeLayerUpdates — shared fixture equivalence', () => {
  for (const fx of fixtures.fixtures) {
    it(`fixture: ${fx.name}`, () => {
      const rows: LayerRow[] = fx.rows.map((r: any) => ({
        id: r.id, kind: r.kind, level: r.level, hasLeafChildren: r.hasLeafChildren,
      }))
      const roleMap = new Map<string, LayerRole>(Object.entries(fx.roles) as [string, LayerRole][])
      const updates = computeLayerUpdates(rows, roleMap)
      const actual: Record<string, unknown> = {}
      for (const [k, v] of updates) actual[k] = v
      expect(actual).toEqual(fx.updates)
    })
  }
})
```

If your TS config doesn't allow JSON imports by default, add `"resolveJsonModule": true` to `frontend/tsconfig.json` — check first; it's almost certainly already enabled in a Vite project.

- [ ] **Step 5: Run frontend tests**

Run:
```bash
cd frontend && npm run test -- --run tests/unit/utils/layerMark.spec.ts
```

Expected: all existing + new fixture cases pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/utils/layerMark.ts frontend/src/store/procedureEditor.ts frontend/tests/unit/utils/layerMark.spec.ts
git commit -m "$(cat <<'EOF'
refactor(layer): validateLayerQ25 groups by walk terminal state

Backend apply-layer-roles now actually executes leaf-reparent, so
dry-run validator switches from 'originalParent' (DB pre-state) to
walk's u.parent_id (post-apply state). LayerRow.originalParent field
+ store population removed. Tests updated; new fixture-driven case
asserts walk equivalence with backend.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Frontend API client + types

**Files:**
- Modify: `frontend/src/api/procedures.ts`
- Modify: `frontend/src/types/node.ts` (or create one if absent)

- [ ] **Step 1: Inspect existing types file for adjacent type style**

Run:
```bash
grep -n "ApplyMarksResult\|export interface\|export type" frontend/src/types/node.ts | head -10
```

- [ ] **Step 2: Add types**

Append to `frontend/src/types/node.ts`:

```typescript
export type LayerApplyRoleValue = 'chapter_1' | 'chapter_2' | 'chapter_3' | 'content' | 'keep'

export interface LayerApplyIn {
  roles: Record<string, LayerApplyRoleValue>
}

export interface LayerApplyResult {
  chapter_map: Record<string, string>
  revision: number
}

export interface LayerApplyConflictDetail {
  code: 'SIBLING_TYPE_CONFLICT'
  message: string
  conflicts: Array<{
    parent_id: string | null
    chapter_children: string[]
    leaf_children: string[]
  }>
}
```

- [ ] **Step 3: Add API client method**

Append to `frontend/src/api/procedures.ts`:

```typescript
import type { LayerApplyIn, LayerApplyResult } from '@/types/node'

export const applyLayerRolesApi = async (
  id: string,
  payload: LayerApplyIn,
  revision: number,
): Promise<LayerApplyResult> =>
  (
    await http.post<LayerApplyResult>(`/procedures/${id}/apply-layer-roles`, payload, {
      headers: { 'If-Match': String(revision) },
    })
  ).data
```

(If `LayerApplyIn` / `LayerApplyResult` is already imported through the namespace at the top, merge into that import line.)

- [ ] **Step 4: Verify frontend type-checks**

Run:
```bash
cd frontend && npx vue-tsc --noEmit
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/procedures.ts frontend/src/types/node.ts
git commit -m "$(cat <<'EOF'
feat(layer-apply): frontend API client + types

applyLayerRolesApi posts to POST /procedures/{id}/apply-layer-roles
with If-Match header; LayerApplyResult mirrors backend response.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Frontend store — rewrite applyLayerRoles

**Files:**
- Modify: `frontend/src/store/procedureEditor.ts` (action at line 867)

- [ ] **Step 1: Locate current applyLayerRoles**

Open `frontend/src/store/procedureEditor.ts` at line 867. Read lines 867-931 to understand the full current implementation before replacing.

- [ ] **Step 2: Replace the action body**

Replace lines 867-931 with:

```typescript
    async applyLayerRoles(roleMap: Map<string, LayerRole>): Promise<{ ok: true } | { ok: false; conflicts: LayerConflict[] }> {
      const rows = this.layerRows
      const updates = computeLayerUpdates(rows, roleMap)
      const conflicts = validateLayerQ25(rows, updates)
      if (conflicts.length > 0) return { ok: false, conflicts }

      const idMap = await this.ensureSaved()
      this.pushUndo('layer')

      const resolvedRoles: Record<string, LayerRole> = {}
      for (const [id, role] of roleMap) {
        resolvedRoles[idMap[id] ?? id] = role
      }

      try {
        await applyLayerRolesApi(this.procedure!.id, { roles: resolvedRoles }, this.revision)
      } catch (e: unknown) {
        // 后端 400 SIBLING_TYPE_CONFLICT 详情:{ code, message, conflicts: [...] }
        const detail = (e as { response?: { status?: number; data?: { detail?: { code?: string; conflicts?: unknown[] } } } })?.response?.data?.detail
        if (detail?.code === 'SIBLING_TYPE_CONFLICT' && Array.isArray(detail.conflicts)) {
          const conflicts = detail.conflicts.map((c: any) => ({
            parent_id: c.parent_id,
            chapterChildren: c.chapter_children,
            leafChildren: c.leaf_children,
          })) as LayerConflict[]
          return { ok: false, conflicts }
        }
        throw e
      }

      await this.reload()
      this.layerMode = false
      return { ok: true }
    },
```

- [ ] **Step 3: Update imports at top of the file**

In `frontend/src/store/procedureEditor.ts`, find the imports block and:
- Remove: `import { convertStepToChapter } from '@/api/steps'` (unless used elsewhere — verify with grep first)
- Add: `import { applyLayerRolesApi } from '@/api/procedures'`

Verify other refs:

```bash
grep -n "convertStepToChapter" frontend/src/store/procedureEditor.ts
```

If `convertStepToChapter` still appears in `store.convertToChapter` (line 754-758), keep the import — that action is still defined even if unused by UI; do not remove it as part of this task.

- [ ] **Step 4: Run vue-tsc + the store spec**

Run:
```bash
cd frontend && npx vue-tsc --noEmit
```

Expected: no errors. If errors mention removed `originalParent` somewhere we missed, fix those refs.

- [ ] **Step 5: Rewrite `procedureEditor.applyLayerRoles.spec.ts`**

This file (at `frontend/tests/unit/store/procedureEditor.applyLayerRoles.spec.ts`) currently mocks `convertStepToChapter` per row. With the new single-endpoint flow it needs to mock `applyLayerRolesApi` instead. Replace its content with:

```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('@/api/http', () => ({ http: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() } }))

vi.mock('@/api/procedures', async () => {
  const actual = await vi.importActual<typeof import('@/api/procedures')>('@/api/procedures')
  return {
    ...actual,
    applyLayerRolesApi: vi.fn(async () => ({ chapter_map: {}, revision: 2 })),
  }
})

import { useProcedureEditorStore } from '@/store/procedureEditor'

const baseProc = { id: 'p1', revision: 1, lock_version: 1 } as any

describe('store.applyLayerRoles (overlay)', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('Q25 末态冲突 → 返回 conflicts,不调 API', async () => {
    const { applyLayerRolesApi } = await import('@/api/procedures')
    ;(applyLayerRolesApi as unknown as ReturnType<typeof vi.fn>).mockClear()
    const store = useProcedureEditorStore()
    store.procedure = baseProc
    store.chapters = [{ id: 'A', parent_id: null, title: 'A', skip_numbering: false, mark_status: 'unmarked', sort_order: 0 }]
    // s1 + s2 都在 A 下,s1 升 L2,s2 保持 — walk 末态 s2 挂到 s1 下 → 无冲突;
    // 构造冲突需要根级 leaf,这里换成 A + 兄弟章节 B + 一个根级 leaf k 保持:
    store.chapters.push({ id: 'B', parent_id: null, title: 'B', skip_numbering: false, mark_status: 'unmarked', sort_order: 1 })
    store.steps = [
      { id: 'k', chapter_id: null, kind: 'content', title: '', content: '<p>x</p>', input_schema: {} as never, attachment_marks: [], skip_numbering: false, sort_order: 0 },
    ]
    const result = await store.applyLayerRoles(new Map([['A', 'chapter_1'], ['B', 'chapter_1']]))
    // 根级 null 下 [A, B](chapters) + [k](leaf) — 末态冲突
    expect(result.ok).toBe(false)
    expect(applyLayerRolesApi).not.toHaveBeenCalled()
  })

  it('happy path → 调用 applyLayerRolesApi 一次并 reload', async () => {
    const { applyLayerRolesApi } = await import('@/api/procedures')
    ;(applyLayerRolesApi as unknown as ReturnType<typeof vi.fn>).mockClear()
    const store = useProcedureEditorStore()
    store.procedure = baseProc
    store.chapters = [{ id: 'A', parent_id: null, title: 'A', skip_numbering: false, mark_status: 'unmarked', sort_order: 0 }]
    store.steps = [
      { id: 's1', chapter_id: 'A', kind: 'content', title: 'X', content: '', input_schema: {} as never, attachment_marks: [], skip_numbering: false, sort_order: 0 },
    ]
    vi.spyOn(store, 'ensureSaved').mockResolvedValue({})
    vi.spyOn(store, 'reload').mockResolvedValue()
    const result = await store.applyLayerRoles(new Map([['A', 'chapter_1'], ['s1', 'chapter_2']]))
    expect(result.ok).toBe(true)
    expect(applyLayerRolesApi).toHaveBeenCalledTimes(1)
    expect(applyLayerRolesApi).toHaveBeenCalledWith('p1', { roles: { A: 'chapter_1', s1: 'chapter_2' } }, 1)
    expect(store.reload).toHaveBeenCalled()
    expect(store.layerMode).toBe(false)
  })

  it('后端 400 SIBLING_TYPE_CONFLICT → 解构 detail 并返回 conflicts', async () => {
    const { applyLayerRolesApi } = await import('@/api/procedures')
    ;(applyLayerRolesApi as unknown as ReturnType<typeof vi.fn>).mockRejectedValueOnce({
      response: { status: 400, data: { detail: { code: 'SIBLING_TYPE_CONFLICT', message: 'x', conflicts: [
        { parent_id: 'A', chapter_children: ['s1'], leaf_children: ['k'] }
      ]}}}
    })
    const store = useProcedureEditorStore()
    store.procedure = baseProc
    store.chapters = [{ id: 'A', parent_id: null, title: 'A', skip_numbering: false, mark_status: 'unmarked', sort_order: 0 }]
    store.steps = [
      { id: 's1', chapter_id: 'A', kind: 'content', title: 'X', content: '', input_schema: {} as never, attachment_marks: [], skip_numbering: false, sort_order: 0 },
    ]
    vi.spyOn(store, 'ensureSaved').mockResolvedValue({})
    vi.spyOn(store, 'reload').mockResolvedValue()
    const result = await store.applyLayerRoles(new Map([['A', 'chapter_1'], ['s1', 'chapter_2']]))
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.conflicts[0].parent_id).toBe('A')
      expect(result.conflicts[0].chapterChildren).toEqual(['s1'])
      expect(result.conflicts[0].leafChildren).toEqual(['k'])
    }
  })
})
```

Note: the store exposes `revision` as a getter (`procedureEditor.ts:201`) which returns `procedure.revision ?? 0`. The new `applyLayerRoles` uses `this.revision` for the If-Match value. Tests set `store.procedure = baseProc` where `baseProc.revision = 1`.

Run:
```bash
cd frontend && npm run test -- --run tests/unit/store/procedureEditor.applyLayerRoles.spec.ts
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/store/procedureEditor.ts
git commit -m "$(cat <<'EOF'
feat(layer-apply): rewrite store.applyLayerRoles to single endpoint

Collapse the prior 3-step (per-row convert + in-memory reorder)
implementation into one transactional POST /apply-layer-roles call.
Backend now owns the walk + Phase A-D execution + numbering recompute;
frontend only resolves temp→real ids and reloads on success. Q25
conflicts surfaced from backend 400 detail map back to LayerConflict[]
for the existing banner.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: Run full backend + frontend test suites + lint

**Files:** None (verification only)

- [ ] **Step 1: Backend full unit test pass**

Run:
```bash
backend/.venv/bin/python -m pytest backend/tests/unit -q
```

Expected: all green. Fix any regressions before proceeding (most likely candidates: `test_conversion_service.py` if you accidentally touched shared helpers; `test_step_service.py` if you adjusted `_assert_can_hold_steps`).

- [ ] **Step 2: Frontend full unit test pass**

Run:
```bash
cd frontend && npm run test -- --run
```

Expected: all green.

- [ ] **Step 3: Frontend lint + typecheck**

Run:
```bash
cd frontend && npm run lint && npx vue-tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Backend lint (ruff/mypy if configured)**

Run:
```bash
backend/.venv/bin/python -m ruff check backend/app/services/layer_apply_service.py backend/app/services/layer_walk.py backend/app/routers/procedures.py 2>/dev/null || echo "(ruff not configured)"
backend/.venv/bin/python -m mypy backend/app/services/layer_apply_service.py 2>/dev/null || echo "(mypy not configured)"
```

Fix any reported issues.

If everything is green, no commit needed — verification step only. If you had to fix lint issues, commit:

```bash
git commit -am "chore(layer-apply): lint fixes"
```

---

## Task 14: Manual dev verification — screenshot scenario in running app

**Goal:** Reproduce the user's original screenshot scenario in the dev environment and confirm 3.1/3.2/3.3 promote correctly with auto-nest.

**Reference skill:** `running-smartsop-dev` — covers how to launch + which routes/ports + chrome-devtools MCP driving.

- [ ] **Step 1: Launch dev stack**

Follow the running-smartsop-dev skill — start backend (FastAPI on 8000) + frontend (Vite on 5173).

- [ ] **Step 2: Set up the screenshot scenario**

Either:
- (a) Import a Word file with `3.0 职责` + 三个人名 + 描述结构, OR
- (b) Manually create a procedure via UI with the same shape, OR
- (c) Use chrome-devtools MCP to drive setup against a fresh dev DB.

- [ ] **Step 3: Enter layer mode, pick 3.1/3.2/3.3 = 二级, click 应用层级**

Expected:
- No §Q25 banner.
- Tree updates to show three L2 chapters under 3.0 职责, each with 2 content children.
- Numbering 3.1/3.2/3.3 preserved.

- [ ] **Step 4: Check backend log for errors**

Verify the FastAPI log shows a single `POST /api/v1/procedures/{id}/apply-layer-roles 200` line, no 4xx/5xx.

- [ ] **Step 5: Refresh the page — confirm persistence**

The tree should reload from DB with the same structure. If it doesn't, there's a persistence bug; investigate before continuing.

---

## Task 15: Update memory + final commit

**Files:**
- Modify: `~/.claude/projects/-Users-yuming-Desktop-claude-projects-HP-smart-sop-SmartSOP/memory/layer-overlay-q25-dryrun-gap.md`
- Modify: `~/.claude/projects/-Users-yuming-Desktop-claude-projects-HP-smart-sop-SmartSOP/memory/MEMORY.md`

- [ ] **Step 1: Mark the old memory SUPERSEDED**

Read `~/.claude/projects/-Users-yuming-Desktop-claude-projects-HP-smart-sop-SmartSOP/memory/layer-overlay-q25-dryrun-gap.md` and prepend:

```markdown
> **SUPERSEDED (2026-05-27):** This memory described the rationale for grouping `validateLayerQ25` by `originalParent` (because the backend single-row `convert-to-chapter` API did not move leaves). With `POST /procedures/{id}/apply-layer-roles` (spec `2026-05-27-layer-overlay-auto-nest-design.md`) the backend now executes `leaf-reparent` via Phase D, and the validator groups by walk terminal state (`u.parent_id`). The `LayerRow.originalParent` field has been removed. Keep this memory only for historical context.
```

- [ ] **Step 2: Update MEMORY.md index line**

In `~/.claude/projects/-Users-yuming-Desktop-claude-projects-HP-smart-sop-SmartSOP/memory/MEMORY.md`, change the line:

```
- [Layer overlay Q25 dry-run gap](layer-overlay-q25-dryrun-gap.md) — 已修：LayerRow 加 originalParent，validateLayerQ25 按 row 终态（walk parent / DB 原父）分组，匹配 store + 后端单行 API 的实际语义
```

to:

```
- [Layer overlay Q25 dry-run gap](layer-overlay-q25-dryrun-gap.md) — SUPERSEDED 2026-05-27 by auto-nest spec; validator now groups by walk terminal state and leaves are actually reparented
```

- [ ] **Step 3: No git commit for memory (it lives outside repo). Final repo state check:**

Run:
```bash
git log --oneline a250fdb..HEAD
```

Expected: 8–10 commits, one per major task. Push when ready (only with user confirmation).

---

## Self-Review Checklist (for the engineer executing the plan)

Before declaring done:

- [ ] Spec §1.2 收养规则 — covered by Task 5 (Phase A) + Task 7 (Phase D) + fixture in Task 1.
- [ ] Spec §3.2 Phase A parent_id resolution via map — covered by Task 5 (test `phase_a` happy path + Task 8 `l2_then_l3_nested_adoption`).
- [ ] Spec §3.2 Phase C CHAPTER_HAS_CHILDREN — covered by Task 6.
- [ ] Spec §3.2 to-content empty title → empty body — covered by Task 8.
- [ ] Spec §4.2 validateLayerQ25 realignment — covered by Task 10.
- [ ] Spec §4.1 store action signature unchanged — covered by Task 12 (`{ok,conflicts}` return shape preserved).
- [ ] Spec §5.2 frontend tests — covered by Task 10 (fixture-driven + rewritten Q25 cases).
- [ ] Spec §7 acceptance #5 — covered by Task 15 memory update.

If any item above isn't covered, add a task before the verification phase.
