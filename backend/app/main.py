"""FastAPI 应用入口（Phase 1）。

装配：日志、CORS、request-id 中间件、健康检查。后续阶段在此挂载各 router。
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.db import SessionLocal, engine
from app.logging_config import configure_logging
from app.seed import run_seed
from app.middleware import RequestIdMiddleware
from app.routers import (
    attachments,
    audit_logs,
    fields,
    folders,
    nodes,
    parse,
    procedure_groups,
    procedures,
)
from app.routers import settings as settings_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    logger.info("Smart SOP API starting env=%s", settings.app_env)
    # 启动时幂等 seed 系统种子数据（system folders / settings / sample field）。
    # seed.run_seed 自身幂等，重复运行不会重复插入。
    with SessionLocal() as db:
        run_seed(db)
    yield
    logger.info("Smart SOP API shutting down")


app = FastAPI(
    title="Smart SOP API",
    version="0.1.0",
    description="独立的结构化 SOP 管理系统 API。",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    """统一参数校验错误为 {code, message, field} 信封（api-specification §4.4）。"""
    errors = exc.errors()
    first = errors[0] if errors else {}
    loc = [str(p) for p in first.get("loc", []) if p not in ("body", "query", "path")]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": {
                "code": "VALIDATION_FAILED",
                "message": first.get("msg", "参数校验失败"),
                "field": ".".join(loc) or None,
            }
        },
    )


app.include_router(folders.router)
app.include_router(audit_logs.router)
app.include_router(procedures.router)
app.include_router(procedure_groups.router)
app.include_router(parse.router)
app.include_router(attachments.router)
app.include_router(fields.router)
app.include_router(settings_router.router)
app.include_router(nodes.router)


@app.get("/healthz", tags=["health"])
def healthz() -> dict[str, str]:
    """Liveness probe - 仅检查应用是否存活。"""
    return {"status": "ok"}


@app.get("/readyz", tags=["health"])
def readyz() -> JSONResponse:
    """Readiness probe - 检查数据库连通性。"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        logger.exception("readiness check failed: database unreachable")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unavailable", "db": "down"},
        )
    return JSONResponse(content={"status": "ok", "db": "up"})
