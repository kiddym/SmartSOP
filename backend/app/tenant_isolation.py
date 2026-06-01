"""SQLAlchemy event listeners enforcing row-level tenant isolation.

Registered on the global Session class so every session (app + tests) is
covered. Skipped when no tenant context is set (pre-auth flows) or bypassed.
"""

from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.orm import Session, with_loader_criteria

from app import tenant
from app.models.base import Base, TenantScoped


def _before_flush(session, flush_context, instances) -> None:
    """Auto-stamp company_id on new tenant-scoped rows that lack one."""
    if tenant.is_bypassed():
        return
    company_id = tenant.get_current_company_id()
    if company_id is None:
        return
    for obj in session.new:
        if isinstance(obj, TenantScoped) and getattr(obj, "company_id", None) is None:
            obj.company_id = company_id


def _tenant_scoped_mappers() -> list[type]:
    """All mapped classes that participate in tenant scoping (TenantScoped subclasses)."""
    return [m.class_ for m in Base.registry.mappers if issubclass(m.class_, TenantScoped)]


def _do_orm_execute(execute_state) -> None:
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
