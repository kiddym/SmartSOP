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
from app.middleware import RequestIdMiddleware
from app.parser.utils import images
from app.routers import (
    analytics,
    asset_categories,
    assets,
    attachments,
    audit_logs,
    auth,
    batch_imports,
    company,
    cost_categories,
    customers,
    fields,
    folders,
    heading_rules,
    locations,
    meters,
    multi_parts,
    nodes,
    notification_preferences,
    notifications,
    parse,
    part_categories,
    part_consumptions,
    parts,
    preventive_maintenances,
    procedure_groups,
    procedures,
    purchase_orders,
    requests,
    roles,
    teams,
    users,
    vendors,
    work_orders,
)
from app.routers import settings as settings_router
from app.seed import run_seed
from app.tenant_middleware import TenantContextMiddleware

logger = logging.getLogger(__name__)


def _probe_soffice() -> None:
    """启动探测 LibreOffice 软依赖；缺失记 warning（EMF/WMF 将无法转换）。"""
    if not images.soffice_available():
        logger.warning("LibreOffice (soffice) 不可用：EMF/WMF 矢量图将无法转换，导入时以占位符代替")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    logger.info("Smart CMMS API starting env=%s", settings.app_env)
    # 启动时幂等 seed 系统种子数据（system folders / settings / sample field）。
    # seed.run_seed 自身幂等，重复运行不会重复插入。
    with SessionLocal() as db:
        run_seed(db)
    _probe_soffice()
    yield
    logger.info("Smart CMMS API shutting down")


app = FastAPI(
    title="Smart CMMS API",
    version="0.1.0",
    description="独立的结构化 SOP 管理系统 API。",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(RequestIdMiddleware)
# Sets tenant context from the bearer token for the whole request, so row-level
# isolation is fail-closed by construction (see app/tenant_middleware.py).
app.add_middleware(TenantContextMiddleware)
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


app.include_router(auth.router)
app.include_router(assets.router)
app.include_router(locations.router)
app.include_router(teams.router)
app.include_router(work_orders.router)
app.include_router(requests.router)
app.include_router(preventive_maintenances.router)
app.include_router(meters.router)
app.include_router(part_categories.router)
app.include_router(parts.router)
app.include_router(multi_parts.router)
app.include_router(part_consumptions.router)
app.include_router(cost_categories.router)
app.include_router(vendors.router)
app.include_router(customers.router)
app.include_router(purchase_orders.router)
app.include_router(analytics.router)
app.include_router(notifications.router)
app.include_router(notification_preferences.router)
app.include_router(asset_categories.router)
app.include_router(folders.router)
app.include_router(audit_logs.router)
app.include_router(procedures.router)
app.include_router(procedure_groups.router)
app.include_router(parse.router)
app.include_router(batch_imports.router)
app.include_router(heading_rules.router)
app.include_router(attachments.router)
app.include_router(fields.router)
app.include_router(settings_router.router)
app.include_router(nodes.router)
app.include_router(company.router)
app.include_router(roles.router)
app.include_router(users.router)


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
    return JSONResponse(
        content={
            "status": "ok",
            "db": "up",
            "soffice": "up" if images.soffice_available() else "down",
        }
    )
