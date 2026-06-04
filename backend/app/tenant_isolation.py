"""SQLAlchemy event listeners enforcing row-level tenant isolation.

Registered on the global Session class so every session (app + tests) is
covered. Skipped when no tenant context is set (pre-auth flows) or bypassed.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session, with_loader_criteria

from app import tenant
from app.models.base import Base, TenantScoped


def _before_flush(session: Any, flush_context: Any, instances: Any) -> None:
    """Auto-stamp company_id on new tenant-scoped rows; fail-closed if no context.

    With a tenant context set: stamp any new TenantScoped row that lacks a
    company_id. With no context (and not bypassed): a new TenantScoped row that
    still lacks company_id is a missing-context bug → raise TenantContextMissingError
    rather than let it flush a NULL row / hit an opaque NOT NULL IntegrityError.
    """
    if tenant.is_bypassed():
        return
    company_id = tenant.get_current_company_id()
    for obj in session.new:
        # TenantScoped 覆盖 TenantMixin（NOT NULL）+ NullableTenantMixin（SOP/字典表）；
        # 两者都定义 company_id 列，故对整个 TenantScoped 家族自动补值。getattr/setattr
        # 规避 mypy 在 marker 基类（无 company_id 列）上的 attr-defined。
        if not isinstance(obj, TenantScoped) or getattr(obj, "company_id", None) is not None:
            continue
        if company_id is None:
            raise tenant.TenantContextMissingError(
                f"无 tenant 上下文写入租户行 {type(obj).__name__}；"
                "应经请求认证 / create_company / set_current_company_id 设置上下文，"
                "或显式落 company_id（如附件随宿主）。"
            )
        obj.company_id = company_id  # type: ignore[attr-defined]  # 子类均有 company_id 列


def _tenant_scoped_mappers() -> list[Any]:
    """All mapped classes that participate in tenant scoping (TenantScoped subclasses)."""
    return [m.class_ for m in Base.registry.mappers if issubclass(m.class_, TenantScoped)]


def _do_orm_execute(execute_state: Any) -> None:
    """Auto-scope SELECTs to the current tenant via per-entity loader criteria."""
    if not execute_state.is_select:
        return
    if tenant.is_bypassed():
        return
    company_id = tenant.get_current_company_id()
    if company_id is None:
        return

    # NOTE: We deliberately emit one with_loader_criteria per concrete mapped
    # subclass using a *direct column expression* (cls.company_id == company_id)
    # rather than a single criteria against the TenantScoped marker base with a
    # lambda. with_loader_criteria runs SQLAlchemy's lambda-closure analyzer,
    # which eagerly invokes the lambda against the supplied entity class; the
    # marker base has no company_id column, so that raises AttributeError.
    # Passing concrete classes with a non-lambda expression avoids the analyzer
    # entirely while still varying company_id correctly per execution. Criteria
    # for entities not present in the query are harmless no-ops.
    options = [
        with_loader_criteria(cls, cls.company_id == company_id, include_aliases=True)
        for cls in _tenant_scoped_mappers()
    ]
    if options:
        execute_state.statement = execute_state.statement.options(*options)


def register_tenant_events() -> None:
    """Idempotently attach listeners to the global Session class."""
    if not event.contains(Session, "before_flush", _before_flush):
        event.listen(Session, "before_flush", _before_flush)
    if not event.contains(Session, "do_orm_execute", _do_orm_execute):
        event.listen(Session, "do_orm_execute", _do_orm_execute)


register_tenant_events()
