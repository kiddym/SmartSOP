# Unified Node Model — B4 Contract (Backend) Design

> Phase B4 of the Plan B unified-node-model migration. Predecessors B1/B2a/B2b/B3a/B3b are merged to `main`; the frontend already uses **only** `ProcedureNode`. This phase removes the legacy three-table machinery from the backend and makes `ProcedureNode` the sole persistence model.

**Date:** 2026-05-29
**Status:** Design (approved for spec write)

---

## 1. Goal

Make `ProcedureNode` the single source of truth on the backend. Convert the two remaining legacy *builders* (Word import, version clone/delete) to write nodes directly, split the metadata `PUT` away from the dead batch-save, fix asset-reference scanning to read node bodies, then delete all legacy chapter/step code, drop the two tables, and rebuild `dev.db`.

## 2. Architecture

Two sub-phases, mirroring the B3a/B3b "build the new path, then delete the old" split that worked well:

- **B4a — Node-native paths.** Real code. Convert `import_service` and `version_flow_service` to node-native, split `PUT /procedures/{id}` to metadata-only, fix `asset_service` scanning, port the content-size guard onto node writes, and update the affected tests. Legacy services/tables/endpoints remain present and compiling; the full test suite stays green throughout.
- **B4b — Delete legacy.** Mechanical. Delete 8 legacy services, 2 routers, 2 models, the legacy schemas, the dead endpoints, the `Procedure` relationships and exports; add an Alembic migration dropping the two tables; rebuild `dev.db`; delete the purely-legacy tests. Verified by the suite staying green + a residual-reference grep + a fresh-DB boot (deletion-style, not red-green).

**Tech stack:** FastAPI, SQLAlchemy 2.0 (Mapped/`mapped_column`), Alembic, Pydantic v2, pytest. Python interpreter on this host: `backend/.venv/bin/python` (no `uv`).

## 3. Decisions (from brainstorming)

1. **Phasing:** split into B4a (builders) + B4b (delete). One spec (this doc), two implementation plans.
2. **Validation:** drop the legacy structural rules (Q25 sibling-mutex, `MAX_DEPTH=3`) — they are specific to the chapter/content/step structure and have no equivalent in the unified node model, where parent/depth are *derived* (`node_tree.build_tree`) rather than constrained. **Keep** the 5 MB content-size guard, ported onto `ProcedureNode.body` writes. Field-level validation already exists via `enforce_node_invariants` in `node_service`.

## 4. Scope

### In scope
- `import_service` → build `ProcedureNode` directly from the parse-result tree.
- `version_flow_service` → `_clone_tree` and `delete_group` operate on `ProcedureNode`.
- `PUT /procedures/{id}` → metadata-only (`ProcedureUpdate`), no structural assembly, no legacy numbering.
- `asset_service._scan_referenced_asset_ids` → scan `ProcedureNode.body`.
- Content-size guard ported into `node_service` writes.
- Delete: `chapter_service`, `step_service`, `conversion_service`, `mark_service`, `layer_apply_service`, `numbering_service`, `node_sync`, `editor_service`; routers `chapters.py`, `steps.py`; endpoints `apply-marks`, `apply-layer-roles` (and `convert-*` which live in the deleted routers); models `chapter.py`, `step.py`; legacy schemas; the `Procedure.chapters`/`Procedure.steps` relationships; `models/__init__` exports.
- Alembic migration dropping `tb_procedure_step` then `tb_procedure_chapter`.
- `dev.db` rebuild.
- Update/delete the affected tests.

### Out of scope (explicit non-goals)
- The Word **parser** and its **parse-result DTO** (`schemas/parse.py`, `ImportNodeIn`, the `/parse` preview). The parser naturally produces a chapter/step hierarchy; B4 only changes how that result is *persisted* (nodes, not legacy tables). The import endpoint payload still carries a `chapters` tree.
- The **PDF pipeline** — already node-native (`pdf/context.load_render_data` reads `node_service.get_nodes()`; the `.chapters`/`.steps` in `pdf/*` are render-DTO fields, not ORM).
- The live **node CRUD** endpoints/services (`routers/nodes.py`, `node_service.py`, `node_numbering.py`, `node_tree.py`, `schemas/node_v2.py`) — unchanged except the added size guard.
- Frontend — apart from one TS return-type adjustment for `updateProcedure` (§5.3). The frontend already issues zero legacy-endpoint calls (verified: B3b-2).

---

## 5. B4a — Node-native paths

### 5.1 `import_service.import_procedure` → build nodes directly

**File:** `backend/app/services/import_service.py`

Current flow: `_normalize_for_exclusion` → recursive `_create_node` builds `ProcedureChapter`/`ProcedureStep` → `editor_service._validate_and_recompute_levels` → `numbering_service.recompute` (→ `node_sync` rebuilds nodes). The parser only ever emits `content_type ∈ {chapter, content}` (no `step`).

New flow — flatten the `ImportNodeIn` tree in document (pre-order) order, emitting one `ProcedureNode` per source node:

```python
import html
_SORT_GAP = 1000

def _chapter_body(title: str) -> str:
    title = title.strip()
    return f"<p>{html.escape(title)}</p>" if title else ""

def import_procedure(db, *, name, folder_id, description, chapters, upload_token=None, meta):
    name = name.strip()
    if not name:
        raise unprocessable("VALIDATION_FAILED", "程序名不能为空", field="name")
    proc = procedure_service.create_procedure(db, ProcedureCreate(
        folder_id=folder_id, name=name, level_of_use=_DEFAULT_LEVEL_OF_USE, description=description,
    ), meta)

    seq = 0
    def next_sort() -> int:
        nonlocal seq
        seq += 1
        return seq * _SORT_GAP

    def walk(nodes: list[ImportNodeIn], level: int) -> None:
        for n in nodes:
            if n.content_type == "content":
                db.add(ProcedureNode(
                    procedure_id=proc.id, sort_order=next_sort(),
                    heading_level=None, kind="node",
                    body=_promote_temp_urls(db, proc.id, n.rich_content),
                    skip_numbering=n.skip_numbering, mark_status="unmarked",
                ))
            else:  # chapter (heading container)
                db.add(ProcedureNode(
                    procedure_id=proc.id, sort_order=next_sort(),
                    heading_level=level, kind="node",
                    body=_chapter_body(n.title),
                    skip_numbering=n.skip_numbering,
                    mark_status="review" if n.mark_status == "review" else "unmarked",
                ))
                walk(n.children, level + 1)

    walk(chapters, 1)
    db.flush()
    node_numbering.recompute(db, proc.id)
    asset_service.rebuild_references(db, proc.id)
    source_docx_service.store_from_token(db, procedure_group_id=proc.procedure_group_id, upload_token=upload_token)
    db.flush()
    return proc
```

- This is `node_sync.walk` adapted to a single doc-order loop over the in-memory tree (the legacy version needed two loops because chapters/steps lived in separate tables; the `ImportNodeIn` children are already interleaved in document order).
- **Drop** `_normalize_for_exclusion` / `_relocate_stray_content` — they existed only to satisfy the legacy Q25 mutex (a heading's children must be all sub-headings *or* all content). The node model has no such constraint; keeping content in its original document position is **more** faithful to the source (see §10, behavior change).
- **Drop** the `editor_service._validate_and_recompute_levels` and `numbering_service.recompute` calls. Use `node_numbering.recompute` instead.
- **Imports:** remove `ProcedureChapter`, `ProcedureStep`, `editor_service`, `numbering_service`, `enforce_content_kind_invariant`. Add `ProcedureNode`, `node_numbering`, `html`. Keep `asset_service`, `procedure_service`, `source_docx_service`, `ProcedureCreate`, `ImportNodeIn`, `_promote_temp_urls`.

### 5.2 `version_flow_service` → node-native

**File:** `backend/app/services/version_flow_service.py`

**(a) `_clone_tree(db, src_id, dst_id)`** — replace chapter+step clone with a flat node copy:

```python
_NODE_COPY = (
    "sort_order", "heading_level", "kind", "body",
    "skip_numbering", "input_schema", "attachment_marks",
)

def _clone_tree(db, src_id, dst_id):
    nodes = db.execute(
        select(ProcedureNode)
        .where(ProcedureNode.procedure_id == src_id, ProcedureNode.is_active.is_(True))
        .order_by(ProcedureNode.sort_order, ProcedureNode.id)
    ).scalars()
    for n in nodes:
        db.add(ProcedureNode(
            id=new_uuid(), procedure_id=dst_id,
            mark_status="unmarked",  # mark state is transient editing state; reset clean (matches legacy clone)
            **{f: getattr(n, f) for f in _NODE_COPY},
        ))
    db.flush()
    node_numbering.recompute(db, dst_id)
```

No id/parent remapping needed (parent is derived; nothing stores a node→node FK). `code`/`revision` use model defaults and are recomputed by `node_numbering`.

**(b) `delete_group`** — replace the legacy delete block (the `delete(ProcedureStep…)` + the topological `ProcedureChapter` loop) with a single flat delete:

```python
db.execute(delete(ProcedureNode).where(ProcedureNode.procedure_id == proc.id))
```

Keep the surrounding `ProcedureAssetReference` / `ProcedureAttachment` / `source_docx_service.delete_for_group` / `Procedure` deletions and the audit. **Without this, a post-B4a group-delete would leave orphaned node rows.**

**Imports/constants:** remove `ProcedureChapter`, `ProcedureStep`, `numbering_service`, `_CHAPTER_COPY`, `_STEP_COPY`. Add `ProcedureNode`, `node_numbering`, `_NODE_COPY`. (`delete`, `select`, `new_uuid` already imported.)

### 5.3 Split `PUT /procedures/{id}` to metadata-only

**Files:** `backend/app/routers/procedures.py`, `backend/app/services/procedure_service.py`, `backend/app/schemas/procedure.py`.

The frontend's `updateProcedure` already sends only the `ProcedureUpdate` fields (`name`, `level_of_use`, `description`, `risk_level`, `quality_level`, `custom_values`, `version_update_notes`, `signoff_enabled`); the structural lists in `ProcedureSaveIn` arrive empty.

Add a slim service function (lives in `procedure_service`, so `editor_service` can be deleted whole in B4b):

```python
def update_meta(db, proc_id, data: ProcedureUpdate, expected_revision: int, meta) -> Procedure:
    proc = _get_editable(db, proc_id)            # is_current && DRAFT, else PROCEDURE_READONLY
    optimistic_lock.verify_revision(proc.revision, expected_revision)
    field_service.validate_values(db, data.custom_values, require_check=False)
    proc.name = data.name
    proc.level_of_use = data.level_of_use
    proc.description = data.description
    proc.risk_level = data.risk_level
    proc.quality_level = data.quality_level
    proc.custom_values = data.custom_values
    proc.version_update_notes = data.version_update_notes
    proc.signoff_enabled = data.signoff_enabled   # persists a field the legacy save silently dropped (no competing owner)
    optimistic_lock.bump(proc)
    db.flush()
    audit_service.log_procedure_action(db, target_id=proc.id,
        procedure_group_id=proc.procedure_group_id, action="update", meta=meta, new_value={})
    return proc
```

Router:

```python
@router.put("/{procedure_id}", response_model=ProcedureMeta)
def update_procedure(procedure_id, payload: ProcedureUpdate, db=Depends(get_db),
                     meta=Depends(get_request_meta), if_match: str | None = Header(None, alias="If-Match")):
    expected = ensure_if_match(if_match)
    proc = procedure_service.update_meta(db, procedure_id, payload, expected, meta)
    db.commit()
    return procedure_service.to_meta(db, proc)
```

- **Editable check:** reuse/port `editor_service._get_proc_editable`'s logic (`is_current && status == 'DRAFT'` → else `PROCEDURE_READONLY`) into `procedure_service._get_editable` (or reuse an existing helper if present).
- **Response model `ProcedureMeta`** (was `ProcedureSaveResult` = meta + `id_map`). No node creation, so no `id_map`. **Frontend:** update `frontend/src/api/procedures.ts` `updateProcedure` return type to the meta shape (it already reads only `.revision`); drop any `id_map` reference. `ProcedureSaveResult` is deleted in B4b.
- **`signoff_enabled` (resolved):** no request handler currently persists `proc.signoff_enabled` — the legacy `save_procedure` silently dropped it, and the only writers are `version_flow_service` (copy-on-fork) and `pdf/context` (read). The frontend sends it in the meta payload, so `update_meta` **persists it**, fixing a latent drop. No competing owner exists.

### 5.4 `asset_service._scan_referenced_asset_ids` → node bodies

**File:** `backend/app/services/asset_service.py`

```python
from app.models.node import ProcedureNode

def _scan_referenced_asset_ids(db, procedure_id: str) -> set[str]:
    ids: set[str] = set()
    for (body,) in db.execute(
        select(ProcedureNode.body).where(
            ProcedureNode.procedure_id == procedure_id, ProcedureNode.is_active.is_(True))
    ):
        ids |= extract_asset_ids(body)
    return ids
```

Remove the `ProcedureStep` import if it becomes unused. `rebuild_references` (the caller) is unchanged.

### 5.5 Port content-size guard into `node_service`

**File:** `backend/app/services/node_service.py`

Add a 5 MB body guard (the one validation we keep) wherever `body` is written:

```python
CONTENT_MAX_BYTES = 5 * 1024 * 1024

def _body_size_guard(body: str) -> None:
    if len(body.encode("utf-8")) > CONTENT_MAX_BYTES:
        raise payload_too_large("CONTENT_TOO_LARGE", "节点正文超过 5 MB 上限")
```

Call it in `create_node` (on `data.get("body", "")`) and in `patch_node` (when `"body" in changes`). `batch_update` does not write `body` in practice, but guard it there too if `body` is present, for symmetry. Import `payload_too_large` from `app.errors`.

### 5.6 Update affected tests (B4a)

- `tests/unit/services/test_import_service.py` (+ `tests/integration/test_node_import_dualwrite.py` repurposed/renamed): assert import creates `ProcedureNode` rows with correct `heading_level`/`kind`/`body`/`sort_order`/`mark_status`, no legacy rows; content stays in document order (no relocation).
- `tests/unit/services/test_version_flow_service.py`: assert clone copies nodes; `delete_group` removes node rows (no orphans).
- `tests/integration/test_editor.py` / `tests/unit/services/test_editor_service.py`: replace batch-save tests with meta-only `PUT` tests (meta fields persisted, revision bumped, `If-Match` mismatch → conflict, non-DRAFT → `PROCEDURE_READONLY`); structural payload no longer accepted.
- Asset-scan test: references node bodies.
- New `node_service` test: body > 5 MB → `CONTENT_TOO_LARGE`.

**B4a exit:** every live path is node-native; legacy services/tables/endpoints still present and their unit tests still pass; full backend suite green.

---

## 6. B4b — Delete legacy

### 6.1 Services (delete whole files)
`chapter_service.py`, `step_service.py`, `conversion_service.py`, `mark_service.py`, `layer_apply_service.py`, `numbering_service.py`, `node_sync.py`, `editor_service.py`.

### 6.2 Routers / endpoints
- Delete `backend/app/routers/chapters.py` and `backend/app/routers/steps.py`; remove their `include_router(...)` registrations (in `app/main.py` or the router aggregator). `convert-to-step`/`convert-to-chapter`/`convert-to-content` live in those routers and go with them.
- Delete `apply_marks` and `apply_layer_roles` handlers from `routers/procedures.py`; remove now-unused imports (`mark_service`, `layer_apply_service`, `editor_service`, `ApplyMarksResult`, `LayerApplyIn`, `LayerApplyResult`).

### 6.3 Models
- Delete `backend/app/models/chapter.py`, `backend/app/models/step.py`.
- Remove `Procedure.chapters` and `Procedure.steps` relationships (`models/procedure.py` ~lines 59-61).
- Remove `ProcedureChapter`/`ProcedureStep` imports and `__all__` entries from `models/__init__.py`.

### 6.4 Schemas
- `backend/app/schemas/node.py`: delete legacy `ChapterCreate/Update/Move/Out/TreeNode`, `StepCreate/Update/Move/Out`, `ChapterUpsert`, `StepUpsert`, `ApplyMarksResult`, `LayerApplyIn`, `LayerApplyResult`, `ConversionResult`. **Preserve** any symbol still imported by live code — grep first (e.g. `FORM_TYPES` if `_invariants`/`node_service` use it; live node schemas live in `node_v2.py`). If `node.py` becomes empty, delete it.
- `backend/app/schemas/procedure.py`: delete `ProcedureSaveIn` and `ProcedureSaveResult`; the `PUT` now uses `ProcedureUpdate`/`ProcedureMeta`. Remove `chapters`/`steps` from `ProcedureDetail`; update the `from app.schemas.node import …` line (drop `ChapterTreeNode, ChapterUpsert, StepOut, StepUpsert`).
- `procedure_service.get_detail`: stop assembling the chapter tree / step list; `ProcedureDetail` returns only `procedure`/`attachments`/`fields`/`has_source_docx`. (The frontend already reads structure via `/nodes`.)
- `backend/app/services/_invariants.py`: if `enforce_content_kind_invariant` has no remaining callers after import/editor are gone, delete it; keep `enforce_node_invariants`.
- `schemas/parse.py`: stays (parser DTO). Verify it doesn't import a legacy schema being deleted; if it shares one, give parse its own local definition.

### 6.5 Migration
New Alembic revision — `revision = "drop_legacy_chapter_step"`, `down_revision = "add_procedure_node"` (revision ids in this project are slugs, not date prefixes):

```python
def upgrade():
    op.drop_table("tb_procedure_step")     # has FK chapter_id → tb_procedure_chapter: drop first
    op.drop_table("tb_procedure_chapter")

def downgrade():
    # Best-effort reversibility (dev-only; data is NOT restored). Recreate both tables
    # from their final model definition (models/chapter.py, models/step.py as of
    # 20260526_0001_content_block_as_step): UUID/timestamp/soft-delete mixins + columns:
    #   tb_procedure_chapter: procedure_id, parent_id(self FK), title, code, sort_order,
    #     level, mark_status, skip_numbering, conversion_status (+ indexes)
    #   tb_procedure_step: procedure_id, chapter_id(FK), title, code, content(LONGTEXT),
    #     sort_order, skip_numbering, input_schema(JSON), attachment_marks(JSON), kind (+ indexes)
    ...
```

### 6.6 `dev.db` rebuild
```bash
rm backend/dev.db
cd backend && .venv/bin/alembic upgrade head   # alembic.ini is at backend/alembic.ini
# Seed (system folders 归档/废止) runs from lifespan run_seed on backend startup.
```

### 6.7 Tests (delete purely-legacy)
Delete: `tests/unit/services/test_chapter_service.py`, `test_step_service.py`, `test_conversion_service.py`, `test_mark_service.py`, `test_layer_apply_service.py`, `test_numbering_service.py`, `test_node_sync.py`, and `tests/integration/test_node_sync_dualwrite.py`. (The import/version/editor tests were already converted in B4a §5.6.) Grep `tests/` for residual references to deleted symbols and fix/remove.

---

## 7. Data flow after B4

- **Import:** `/parse` → preview tree (`ImportNodeIn`) → `POST /import` → `import_service` writes `ProcedureNode` rows + `node_numbering.recompute` + `asset_service.rebuild_references` + store source docx.
- **Edit:** frontend `nodeEditor` → granular node endpoints (`POST /procedures/{id}/nodes`, `PATCH /nodes/{id}`, `PATCH …/nodes:batch`, `POST …/nodes/reorder`, `DELETE /nodes/{id}`) → `node_service` (only ProcedureNode; `node_numbering` derives `code`).
- **Metadata:** frontend `procedureEditor` → `PUT /procedures/{id}` (`ProcedureUpdate`) → `procedure_service.update_meta`.
- **Versioning:** `version_flow_service` forks/clones/deletes by copying or deleting `ProcedureNode` rows.
- **Read / PDF:** `GET /procedures/{id}/nodes` and `pdf/context` both read `node_service.get_nodes()`.

`numbering_service` and `node_sync` cease to exist; `node_numbering` is the only numbering engine.

## 8. Error handling

- `update_meta`: `PROCEDURE_READONLY` (non-DRAFT/non-current), optimistic-lock conflict on `If-Match` mismatch, field validation via `field_service.validate_values`.
- `node_service` writes: `CONTENT_TOO_LARGE` (>5 MB body), plus existing `enforce_node_invariants` / `BAD_FIELD` / `NOT_FOUND`.
- Transaction boundaries unchanged: services `flush`, routers `commit`.

## 9. Testing strategy

- **B4a:** TDD. Write node-native expectations first (import emits nodes; version clone/delete on nodes; meta-only PUT; node body-size guard; asset-scan on node bodies), then convert. Suite stays green because legacy code is untouched.
- **B4b:** deletion-style — the suite staying green **is** the test. Order deletions so each commit compiles (delete consumers before the things they import; remove router registrations with the routers). After deletion: full `pytest` green + `grep` shows zero residual references to deleted symbols + fresh `alembic upgrade head` on a new DB + app boots (`import app.main`) + a node-CRUD/import smoke check.

## 10. Risks & deliberate behavior changes

- **Q25 sibling-mutex + `MAX_DEPTH` removed (intentional).** These were structure-specific invariants; the node model derives parent/depth and does not constrain them. This invariant is guarded by a code-review memory (`code-review-verify-post-state`), so the removal is called out explicitly here. No live consumer depends on the rejection behavior (the frontend can no longer construct the forbidden shapes through legacy paths).
- **Import no longer relocates stray content.** Content now persists in its original document position rather than being pushed under a sibling sub-heading. This is more faithful to the source document and consistent with the node model. Snapshot/round-trip tests asserting the old relocation must be updated.
- **Transient (B4a→B4b window):** `GET /procedures/{id}` returns empty `chapters`/`steps` for newly-imported procedures until B4b strips those fields. The frontend already ignores them. No production data (dev `dev.db` is rebuilt).
- **`signoff_enabled` (§5.3):** verify ownership before persisting in `update_meta`.
- **Migration downgrade** does not restore data (dev-only). Acceptable per project norm (rebuild `dev.db`).

## 11. Verification gates

- **B4a merge:** `backend/.venv/bin/python -m pytest -q` green; `ruff`/type checks clean; manual import + edit + version-copy smoke via the running dev stack (see `running-smartsop-dev`).
- **B4b merge:** full `pytest` green; residual-reference grep clean; `rm dev.db && alembic upgrade head` succeeds; backend boots and seeds; `frontend` build/tests unaffected (only the `updateProcedure` return type changed).

## 12. Deliverables

1. This design spec.
2. Two implementation plans:
   - `docs/superpowers/plans/2026-05-29-unified-node-model-b4a-node-native-paths.md`
   - `docs/superpowers/plans/2026-05-29-unified-node-model-b4b-delete-legacy.md`
