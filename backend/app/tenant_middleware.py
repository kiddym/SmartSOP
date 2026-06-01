"""Tenant-context middleware (pure ASGI).

Sets the request-scoped tenant context from the bearer access token for the
WHOLE request, so row-level isolation (the do_orm_execute / before_flush events
in ``app.tenant_isolation``) is active by construction — handlers no longer have
to re-assert the context themselves.

Why pure ASGI (not BaseHTTPMiddleware): a sync endpoint runs in its own
``anyio.to_thread`` task whose contextvar context is *copied* at dispatch. A
pure-ASGI middleware sets the contextvar in the same task that then dispatches
the endpoint, so the value propagates into the endpoint's threadpool task.
BaseHTTPMiddleware runs in a separate task and would not propagate reliably.

No valid access token (SOP endpoints, health checks, login/register) => no
context is set => those paths behave exactly as before (unscoped), preserving
Phase 0 SOP behavior.
"""

from __future__ import annotations

from starlette.types import ASGIApp, Receive, Scope, Send

from app import security, tenant


class TenantContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        company_id = self._company_from_headers(scope.get("headers", []))
        token = tenant.set_current_company_id(company_id)
        try:
            await self.app(scope, receive, send)
        finally:
            tenant.reset_current_company_id(token)

    @staticmethod
    def _company_from_headers(headers: list[tuple[bytes, bytes]]) -> str | None:
        for key, value in headers:
            if key == b"authorization":
                parts = value.decode("latin-1").split()
                if len(parts) == 2 and parts[0].lower() == "bearer":
                    try:
                        claims = security.decode_token(parts[1])
                    except security.TokenError:
                        return None
                    if claims.get("type") == "access":
                        return claims.get("company_id")
                return None
        return None
