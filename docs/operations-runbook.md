# SmartSOP Operations Runbook

This runbook covers local development setup, testing, deployment, and common operational tasks for the SmartSOP system.

---

## 1. Prerequisites

| Requirement | Minimum version | Notes |
|---|---|---|
| Python | 3.11+ | Use pyenv or system package manager |
| Node.js | 18+ | LTS release recommended |
| npm | 9+ | Bundled with Node 18 |
| MySQL | 8.0+ | Production and shared dev environments |
| SQLite | 3.x | Development / tests (no installation needed; bundled with Python) |
| Docker | 24+ | For containerised deployment |
| Docker Compose | v2 (plugin) | `docker compose` (no hyphen) |

---

## 2. Local Development Setup

### Backend

```bash
# From the repository root
cd backend

# Install the package and all dev dependencies
pip install -e ".[dev]"

# Apply all database migrations (creates tables)
alembic upgrade head

# Seed initial reference data (folders, default settings, etc.)
python -m app.seed

# Start the development server with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`. Interactive docs are at `http://localhost:8000/docs`.

> **Tip**: For local dev, set `DATABASE_URL=sqlite:///./dev.db` in a `.env` file in the `backend/` directory to use SQLite without needing a running MySQL instance.

### Frontend

```bash
# From the repository root
cd frontend

# Install all dependencies
npm install

# Start the Vite dev server (proxies /api requests to localhost:8000)
npm run dev
```

The frontend will be available at `http://localhost:5173`.

---

## 3. Running Tests

### Backend Tests

```bash
cd backend
pytest
```

- Tests use SQLite in-memory databases via `StaticPool` — no external database required.
- Test fixtures are in `tests/conftest.py`.
- Coverage report: `pytest --cov=app --cov-report=term-missing`

### Frontend Tests

```bash
cd frontend
npm run test
```

- Uses Vitest.
- Watch mode: `npm run test -- --watch`
- Coverage: `npm run test -- --coverage`

---

## 4. Docker Deployment

The `docker-compose.yml` at the repository root defines four services:

| Service | Description |
|---|---|
| `backend` | FastAPI application (Uvicorn) |
| `frontend` | Nginx serving the built Vue SPA |
| `mysql` | MySQL 8 database |
| `scheduler` | APScheduler process (separate from the API) |

### Start all services

```bash
# Build images and start in detached mode
docker compose up -d --build

# Follow logs for all services
docker compose logs -f

# Follow logs for a specific service
docker compose logs -f backend
```

### Stop all services

```bash
docker compose down
```

### Stop and remove volumes (wipes database data)

```bash
docker compose down -v
```

### Rebuild a single service after code changes

```bash
docker compose up -d --build backend
```

---

## 5. Environment Variables

Create a `.env` file in the repository root (next to `docker-compose.yml`) for Docker Compose, or in `backend/` for local development.

| Variable | Required | Description | Example |
|---|---|---|---|
| `DATABASE_URL` | Yes | SQLAlchemy connection string | `mysql+pymysql://user:pass@mysql:3306/smartsop` |
| `STORAGE_PATH` | Yes | Absolute path for file storage (attachments, assets) | `/data/smartsop` |
| `CORS_ORIGINS` | Yes | Comma-separated list of allowed origins | `http://localhost:5173,https://sop.internal` |
| `APP_ENV` | No | Runtime environment (`development` / `production`) | `production` |
| `VITE_API_BASE_URL` | Frontend only | Base URL for API calls (used at build time) | `http://localhost:8000` |

> **Note**: `STORAGE_PATH` must be a directory that the backend process has read and write access to. In Docker, mount a host volume at this path.

---

## 6. Scheduler Process

The APScheduler service runs as a separate Docker container. It must not be scaled beyond one replica to avoid duplicate task execution.

```yaml
# Relevant section of docker-compose.yml (do not run more than 1 replica)
scheduler:
  deploy:
    replicas: 1
```

### Scheduled Tasks

| Task | Schedule | Description |
|---|---|---|
| `cleanup_uploads` | Every 1 hour | Removes orphaned upload temp files from `STORAGE_PATH/uploads/` |
| `asset_gc` | Daily | Garbage-collects unreferenced image assets from `STORAGE_PATH/assets/` |
| `auto_archive` | Daily | Archives procedures that have been deprecated for longer than the configured retention period |

Task definitions live in `app/tasks/`. To adjust schedules, modify the cron expressions in the task registration code and redeploy the scheduler service.

---

## 7. Database Migrations

All schema changes are managed with Alembic. Migration scripts are in `backend/alembic/versions/`.

### Apply all pending migrations

```bash
cd backend
alembic upgrade head
```

### Roll back the most recent migration

```bash
cd backend
alembic downgrade -1
```

### Roll back to a specific revision

```bash
cd backend
alembic downgrade <revision_id>
```

### Show current migration state

```bash
cd backend
alembic current
```

### Show migration history

```bash
cd backend
alembic history --verbose
```

### Generate a new migration after model changes

```bash
cd backend
alembic revision --autogenerate -m "describe your change here"
```

Always review the generated migration script before applying it — autogenerate does not detect all change types (e.g., column default changes).

---

## 8. Common Operations

### Seeding Initial Data

The seed script populates default folders, global settings, and any required reference data:

```bash
cd backend
python -m app.seed
```

Running the seed script multiple times is safe — it is idempotent.

### Health Endpoints

The backend exposes two health check endpoints:

```bash
# Liveness — returns 200 if the process is running
curl http://localhost:8000/healthz

# Readiness — returns 200 if the DB connection is healthy
curl http://localhost:8000/readyz
```

These endpoints are used by Docker Compose and any load balancer health checks.

### Accessing the API docs

```
http://localhost:8000/docs        # Swagger UI
http://localhost:8000/redoc       # ReDoc
```

### Backing up the database (MySQL)

```bash
docker compose exec mysql mysqldump -u root -p smartsop > backup_$(date +%Y%m%d).sql
```

### Restoring a database backup

```bash
docker compose exec -T mysql mysql -u root -p smartsop < backup_20240101.sql
```

---

## 9. Troubleshooting

### Database connection errors

**Symptom**: Backend logs show `OperationalError: (2003, "Can't connect to MySQL server")` or similar.

**Steps**:
1. Check that the `mysql` service is running: `docker compose ps`
2. Verify `DATABASE_URL` is set correctly in `.env`
3. Confirm the database and user exist: `docker compose exec mysql mysql -u root -p -e "SHOW DATABASES;"`
4. Check MySQL logs: `docker compose logs mysql`

### Storage path permission errors

**Symptom**: File uploads or PDF downloads fail with `PermissionError` or `FileNotFoundError`.

**Steps**:
1. Confirm `STORAGE_PATH` exists and is writable by the backend process user.
2. In Docker, check that the volume is mounted and the container user has write access:
   ```bash
   docker compose exec backend ls -la $STORAGE_PATH
   ```
3. Fix permissions:
   ```bash
   chmod -R 755 /path/to/storage
   chown -R <backend-user> /path/to/storage
   ```

### PDF generation fails — missing font

**Symptom**: PDF export returns a 500 error; backend logs mention `ReportLab`, `font`, or `TTFError`.

**Steps**:
1. ReportLab requires fonts to be available on the server. Check `app/services/pdf/engine.py` for the expected font paths.
2. In Docker, ensure fonts are bundled in the backend image (check the `Dockerfile`).
3. If using custom fonts, copy `.ttf` files to the expected directory and rebuild the backend image.

### CORS errors in the browser

**Symptom**: Browser console shows `Access-Control-Allow-Origin` errors when the frontend calls the API.

**Steps**:
1. Check `CORS_ORIGINS` in your `.env` file. It must include the exact origin the browser uses (including port):
   ```
   CORS_ORIGINS=http://localhost:5173
   ```
2. Restart the backend after changing environment variables.
3. Do not use a trailing slash in origins (e.g., use `http://localhost:5173`, not `http://localhost:5173/`).

### Alembic migration conflicts

**Symptom**: `alembic upgrade head` fails with `Multiple head revisions` or `Target database is not up to date`.

**Steps**:
1. Run `alembic history` to inspect the revision tree.
2. If there are multiple heads (from parallel feature branches), merge them:
   ```bash
   alembic merge heads -m "merge migrations"
   ```
3. Apply the merge migration: `alembic upgrade head`

### Scheduler tasks not running

**Symptom**: Uploads are not cleaned up; auto-archive is not triggering.

**Steps**:
1. Confirm the `scheduler` service is running and has exactly one replica: `docker compose ps scheduler`
2. Check scheduler logs: `docker compose logs scheduler`
3. Verify `DATABASE_URL` and `STORAGE_PATH` are set correctly for the scheduler service (it reads the same `.env`).
