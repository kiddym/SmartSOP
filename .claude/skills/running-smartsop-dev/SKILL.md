---
name: running-smartsop-dev
description: Use when launching, restarting, or driving the SmartSOP dev environment — FastAPI backend on 8000 + Vite/Vue frontend on 5173 — to verify a change in the running app rather than just tests. Covers the routes/ports/venv that are non-obvious without reading the repo, the `--reload` and lifespan-seed gotchas that silently leave new code or seed data out, and the browser-drive recipe via chrome-devtools MCP.
---

# Running SmartSOP Dev

## Overview

SmartSOP = FastAPI backend (uvicorn) + Vue 3 / Vite frontend. To verify a change with eyeballs, both have to be running AND serving the merged code. The mechanical traps below have all bitten in real sessions — capture them once, don't rediscover.

## Quick Reference

| Piece | Command / Value |
|---|---|
| Backend launch | `cd backend && .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000` |
| Frontend launch | `cd frontend && npm run dev` |
| Python interpreter | `backend/.venv/bin/python` (no `uv` on this box — `uv run --project backend` fails) |
| Backend health | `curl http://127.0.0.1:8000/healthz` → `{"status":"ok"}` |
| API prefix | `/api/v1/...` (e.g. `/api/v1/folders`) — bare `/folders` returns 404 |
| Frontend entry route | `http://localhost:5173/procedures/library` — **NOT** `/procedures` (no route, blank page) |
| Logs | `backend.log`, `frontend.log` at repo root |
| Pid files | `backend.pid`, `frontend.pid` — frequently stale, verify with `lsof -nP -iTCP:8000,5173 -sTCP:LISTEN` |
| Test runners | `cd frontend && npm test` (vitest) / `cd backend && .venv/bin/python -m pytest -q` |

## Launch from cold

```bash
# Kill anything stale on 8000 / 5173 first
lsof -ti:8000,5173 | xargs -r kill

# Backend (background)
cd backend && nohup .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 \
  > ../backend.log 2>&1 & echo $! > ../backend.pid
cd ..

# Frontend (background)
cd frontend && nohup npm run dev > ../frontend.log 2>&1 & echo $! > ../frontend.pid
cd ..

# Wait for both
until curl -sf http://127.0.0.1:8000/healthz > /dev/null; do sleep 0.5; done
until curl -sfI http://127.0.0.1:5173/ > /dev/null; do sleep 0.5; done
```

## Drive it, don't just launch it

Per the umbrella `run` skill: **a page that returns 200 isn't a verified feature**. Drive the route the diff touched with chrome-devtools MCP:

```
1. mcp__chrome-devtools__list_pages → reuse existing tab if there, else new_page
2. navigate_page → http://localhost:5173/procedures/library
3. wait_for ["文件夹", "归档"] (or whatever text the change should produce)
4. take_snapshot → confirm the a11y tree has what you expect
5. click → interact (folder select / button)
6. take_screenshot → file under .verify-screenshots/
7. Read the screenshot. Blank canvas = failure to render, even if 200 OK.
```

## Gotchas (each has been hit in real sessions)

### `/procedures` is not a route — `/procedures/library` is
Router redirects `/` → `/procedures/library`. Bare `/procedures` matches nothing; AppSidebar renders, `<router-view>` stays empty. If a screenshot shows only the left nav, you're on the wrong URL.

### `--reload` is mandatory for dev
Without `--reload`, uvicorn doesn't pick up code changes; new endpoints / new seed entries silently miss. Verify with `ps -p $(cat backend.pid) -o command=` — must contain `--reload`.

### Lifespan-seeded data only appears after backend restart
System folders (e.g. `归档`, `废止`) are inserted by `run_seed(db)` inside `lifespan` in `backend/app/main.py`. Hot-reload triggers a process restart (so lifespan + seed re-run), but if backend was started BEFORE a seed-touching merge, the running process predates the code — restart it. `seed.run_seed` is idempotent, so restarting is always safe.

### `dev.db` may be unmigrated
SQLite file `backend/dev.db` is the dev DB. After a migration-bearing commit, run `cd backend && .venv/bin/alembic upgrade head` BEFORE restarting uvicorn, or startup will crash on schema mismatch. Most feature branches don't add migrations, but check `backend/alembic/versions/` for recent files when in doubt.

### Pid files lie
`backend.pid` / `frontend.pid` are written by older launch scripts and routinely point at dead PIDs from previous sessions. Source of truth is `lsof -nP -iTCP:8000,5173 -sTCP:LISTEN`. uvicorn `--reload` runs a parent + worker; killing the parent is enough.

### No `uv` available locally
Repo docs and some tooling assume `uv run --project backend ...`. On this host `uv` is missing — use `backend/.venv/bin/python` (and `backend/.venv/bin/pytest`, `backend/.venv/bin/alembic`, `backend/.venv/bin/uvicorn`). Memory `uv-missing-use-venv-python` records this.

## Common Mistakes

| Mistake | Fix |
|---|---|
| Navigating to `/procedures` and screenshotting a blank canvas | Use `/procedures/library` |
| Hitting `curl localhost:8000/folders` and getting 404 | Add `/api/v1/` prefix |
| Reading old pid file and concluding dev is dead | `lsof -nP -iTCP:8000,5173 -sTCP:LISTEN` |
| Verifying a feature on a backend started before the relevant merge | Restart uvicorn so lifespan re-runs |
| Running `uv run --project backend pytest` | Use `backend/.venv/bin/python -m pytest -q` |

## Red Flags

- Screenshot shows only AppSidebar / left rail, nothing in main → wrong route
- Backend returns 404 on a router you just added → forgot `/api/v1/` prefix in curl, or backend wasn't restarted
- Feature works locally but new system folders missing → backend was started before the seed commit; restart
- Tests pass but UI doesn't reflect a change → frontend tab still has cached chunks; hard-reload with `navigate_page type=reload ignoreCache=true`
