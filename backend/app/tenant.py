"""Request-scoped tenant context backed by contextvars.

Company ids are UUID strings (see UUIDMixin). None means "no tenant scope"
(pre-auth flows like login/register).
"""

from __future__ import annotations

import contextlib
from collections.abc import Generator
from contextvars import ContextVar, Token

_company_id: ContextVar[str | None] = ContextVar("company_id", default=None)
_bypass: ContextVar[bool] = ContextVar("tenant_bypass", default=False)


def get_current_company_id() -> str | None:
    return _company_id.get()


def set_current_company_id(company_id: str | None) -> Token[str | None]:
    return _company_id.set(company_id)


def reset_current_company_id(token: Token[str | None]) -> None:
    _company_id.reset(token)


def is_bypassed() -> bool:
    return _bypass.get()


@contextlib.contextmanager
def bypass_tenant_scope() -> Generator[None, None, None]:
    """Temporarily disable tenant scoping (platform-admin / pre-auth lookups)."""
    token = _bypass.set(True)
    try:
        yield
    finally:
        _bypass.reset(token)
