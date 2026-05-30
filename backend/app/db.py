"""数据库引擎与会话管理（Phase 1）。

生产使用 MySQL（settings.database_url）。测试在 conftest 里自建 SQLite 引擎，
不复用此处的 engine。create_engine 是惰性的，import 本模块不会触发实际连接。
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
import app.tenant_isolation  # noqa: F401  registers tenant events

engine = create_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_pre_ping=True,
    echo=settings.database_echo,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
    class_=Session,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：每请求一个 session，结束后关闭并清理租户上下文。"""
    from app import tenant

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        tenant.set_current_company_id(None)
