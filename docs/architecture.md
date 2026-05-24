# SmartSOP Architecture

## 1. System Overview

SmartSOP is an internal Standard Operating Procedure (SOP) management system built for intranet deployment. It allows operations and quality teams to:

- Author, version, and publish SOPs with rich text content and attachments
- Organise procedures into folder hierarchies
- Track the full lifecycle of each procedure (draft → published → deprecated)
- Import existing SOPs from Word documents via a guided wizard
- Export procedures to PDF
- Maintain an audit trail of all significant actions

The system is intended for small-to-medium internal teams. There is no public-facing component and no user authentication — all access is trusted by design (intranet only).

---

## 2. Technology Stack

### Backend
- **Runtime**: Python 3.11+
- **Web framework**: FastAPI (ASGI, served by Uvicorn)
- **ORM**: SQLAlchemy 2.0 with `mapped_column` declarative style
- **Schema / validation**: Pydantic v2
- **Migrations**: Alembic
- **Scheduler**: APScheduler (runs as a separate process/service)
- **PDF generation**: ReportLab

### Frontend
- **Framework**: Vue 3 (Composition API + `<script setup>`)
- **Language**: TypeScript
- **Build tool**: Vite
- **UI component library**: Element Plus
- **State management**: Pinia
- **Rich text editor**: WangEditor
- **HTTP client**: Axios

### Database & Storage
- **Production database**: MySQL 8+
- **Test database**: SQLite (in-memory, StaticPool)
- **File storage**: Local filesystem under `STORAGE_PATH` (attachments + image assets)

### Infrastructure
- **Containerisation**: Docker + Docker Compose (four services: backend, frontend, MySQL, scheduler)

---

## 3. High-Level Architecture

```
Browser (Vue 3 SPA)
        │  HTTP/JSON (Axios)
        ▼
FastAPI application  (/api/v1/*)
        │
        ├── Routers  (request parsing, auth-free, call services)
        │
        ├── Services (business logic, DB writes via flush only)
        │
        ├── SQLAlchemy ORM  (mapped_column models)
        │
        └── MySQL (production) / SQLite (tests)
                          │
                    Local filesystem
                  (STORAGE_PATH — attachments, assets)

APScheduler process (separate container)
        │
        └── Periodic tasks: upload cleanup, asset GC, auto-archive
```

The frontend is a single-page application served by Nginx (or Vite dev server locally). All data access goes through the FastAPI REST API. There is no server-side rendering.

---

## 4. Backend Structure

### Routers → Services → Models

All API routes live in `app/routers/` and are registered under the `/api/v1` prefix via `APIRouter`. Routers are responsible for:

- Deserialising request bodies with Pydantic schemas
- Calling one or more service functions
- Calling `db.commit()` to finalise the transaction
- Returning HTTP responses

Services (in `app/services/`) contain all business logic. They:

- Accept a SQLAlchemy `Session` object
- Perform reads, inserts, and updates
- Call `db.flush()` (not `commit`) so the router controls transaction boundaries
- Raise `HTTPException` for domain-level errors

Models (in `app/models/`) use SQLAlchemy 2.0 `DeclarativeBase` with `mapped_column` annotations.

### DB Session Handling

A FastAPI dependency (`get_db`) yields a `Session` per request. Routers receive the session via dependency injection and call `db.commit()` after service calls complete. On error, SQLAlchemy rolls back automatically when the session context exits.

### Optimistic Locking

Concurrent edits are prevented using an `If-Match` header pattern:

- Each mutable resource carries a `revision` integer field in the database.
- On read, the client receives the current `revision` value.
- On update, the client sends `If-Match: <revision>`. The service checks the stored revision matches; if not, it returns `409 Conflict`.
- On successful write, the revision is incremented.

This is used for procedures, folders, and global settings.

### Soft Delete

Records are never physically deleted. Instead:

- `is_active` is set to `False`
- `deleted_at` is set to the current UTC timestamp

All queries filter on `is_active = True` by default. This preserves referential integrity and audit history.

### Audit Logging

Two audit helpers in `audit_service` record significant actions:

- `log_folder_action(db, folder_id, action, detail)` — folder create/update/delete/reorder
- `log_procedure_action(db, procedure_id, action, detail)` — procedure lifecycle events

Audit records are queryable via `/api/v1/audit_logs` and exportable as CSV.

### Backend Routers Reference

| Router | Prefix | Responsibilities |
|---|---|---|
| `folders` | `/api/v1/folders` | Folder CRUD, reorder, audit |
| `procedures` | `/api/v1/procedures` | Procedure CRUD, version flow (upgrade/rollback/deprecate/restore/copy), PDF |
| `procedure_groups` | `/api/v1/procedure_groups` | Version group listing |
| `chapters` | `/api/v1/chapters` | Chapter CRUD, move, tree |
| `steps` | `/api/v1/steps` | Step CRUD, move |
| `attachments` | `/api/v1/attachments` | File upload/download/delete (per procedure) |
| `fields` | `/api/v1/fields` | Custom field CRUD, batch ops, reorder |
| `settings` | `/api/v1/settings` | Singleton global settings (GET/PUT with If-Match) |
| `audit_logs` | `/api/v1/audit_logs` | Audit log query, CSV export |
| `parse` | `/api/v1/parse` | Word document parsing, import wizard |
| `assets` | `/api/v1/assets` | Procedure image assets (direct upload) |

---

## 5. Frontend Structure

### State Management (Pinia)

Each major domain has a dedicated Pinia store:

- `useFolderStore` — folder tree, CRUD actions
- `useProcedureStore` — procedure list, current procedure, version list
- `useChapterStore` — chapter tree for the current procedure
- `useFieldStore` — custom field definitions
- `useSettingsStore` — global settings singleton
- `useAuditStore` — audit log pagination and filters

Stores call the API layer (Axios wrappers in `src/api/`) and hold reactive state that views bind to.

### Routing (Vue Router)

| Route | View | Purpose |
|---|---|---|
| `/procedures/library` | LibraryView | Published procedure list |
| `/procedures/drafts` | DraftsView | Draft procedure list |
| `/procedures/import` | ImportWizardView | 5-step Word import wizard |
| `/procedures/:id` | ProcedureDetailView | Detail, version list, PDF preview |
| `/procedures/:id/edit` | EditorView | Full editor (chapter tree + content + details + attachments) |
| `/procedures/:id/view` | ViewerView | Read-only procedure view |
| `/folders` | FoldersView | Folder tree management |
| `/settings` | SettingsView | Global settings form |
| `/settings/fields` | FieldsView | Custom field management |
| `/audit-logs` | AuditLogsView | Audit log viewer (folder + procedure tabs) |

### UI Components

Element Plus provides the base component library (tables, forms, dialogs, tabs, tree). WangEditor is embedded in the chapter/step editor for rich text authoring. All components are written in Vue 3 `<script setup>` style with TypeScript.

### API Layer

`src/api/` contains typed Axios wrappers grouped by domain (e.g., `procedures.ts`, `folders.ts`, `chapters.ts`). All requests go to the same origin by default; the base URL is configured via Vite environment variables (`VITE_API_BASE_URL`).

---

## 6. Key Design Decisions

### No Authentication

SmartSOP is deployed on a closed intranet. Adding authentication was explicitly out of scope. All endpoints are publicly accessible within the network. If the deployment context changes, authentication middleware can be added at the FastAPI layer without restructuring the rest of the codebase.

### Version Control Model

Each SOP is tracked through a **procedure group** (a logical SOP identity) that contains one or more **procedure versions**:

- A group always has exactly one active published version (or none).
- New versions are created by upgrading an existing published procedure, which creates a new draft under the same group.
- The version history is accessible via `/api/v1/procedure_groups/{group_id}/versions`.

### Procedure Lifecycle States

```
DRAFT  ──publish──►  PUBLISHED  ──deprecate──►  DEPRECATED
  ▲                      │
  │                 upgrade (creates new DRAFT)
  └──────────────────────┘

DEPRECATED  ──restore──►  PUBLISHED
```

- Only one PUBLISHED version per group at a time.
- Rollback transitions a previous version back to PUBLISHED and deprecates the current one.
- Copy creates a new independent DRAFT from any version.

### Word Import Pipeline

The 5-step import wizard allows teams to bring existing Word documents into SmartSOP:

1. Upload `.docx` file → backend parses structure (headings → chapters, body → steps)
2. Preview parsed structure in the wizard UI
3. User maps/adjusts the chapter/step hierarchy
4. User selects target folder and metadata
5. Confirm → procedure created as DRAFT with chapters and steps pre-populated

The parse service uses `python-docx` and heuristics to detect heading levels and list items.

### PDF Generation

PDF export is handled server-side by ReportLab (`app/services/pdf/engine`). The layout engine renders chapters, steps, rich text (stripped to plain text + basic formatting), and custom fields. Fonts must be available on the server filesystem (see Troubleshooting in the runbook).

---

## 7. Data Flow Examples

### Publishing a Procedure

1. Frontend editor calls `PUT /api/v1/procedures/{id}` with `If-Match: <revision>` to save the latest draft content.
2. User clicks "Publish" → frontend calls `POST /api/v1/procedures/{id}/publish`.
3. The `procedures` router calls `version_flow_service.publish(db, procedure_id)`.
4. `version_flow_service` checks that the procedure is in DRAFT state, sets `status = PUBLISHED`, records `published_at`, and calls `audit_service.log_procedure_action(db, id, "publish")`.
5. Router calls `db.commit()`.
6. Frontend Pinia store receives the updated procedure and refreshes the view.

### Importing a Word Document

1. User uploads `.docx` on step 1 of the import wizard → `POST /api/v1/parse/upload`.
2. `parse_service` saves the file under `STORAGE_PATH/uploads/` and returns a `parse_id`.
3. Frontend calls `GET /api/v1/parse/{parse_id}/preview` to fetch the parsed structure (chapters + steps as JSON).
4. User reviews and adjusts the structure in the wizard UI (steps 2–4).
5. On step 5 confirm, frontend calls `POST /api/v1/parse/{parse_id}/import` with the final mapping and metadata.
6. `import_service` creates the folder (if needed), procedure group, procedure record, chapters, and steps in a single transaction.
7. The new procedure appears in the Drafts view.
