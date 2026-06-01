"""邮件后端工厂（Phase 5B）。按 settings.email_backend 返回单例。"""

from __future__ import annotations

from app.config import settings
from app.email.backends import (
    ConsoleBackend,
    EmailBackend,
    MemoryBackend,
    SMTPBackend,
)

_backend: EmailBackend | None = None


def get_email_backend() -> EmailBackend:
    global _backend
    if _backend is None:
        _backend = _build()
    return _backend


def reset_email_backend() -> None:
    global _backend
    _backend = None


def _build() -> EmailBackend:
    kind = settings.email_backend
    if kind == "smtp":
        return SMTPBackend(
            host=settings.smtp_host,
            port=settings.smtp_port,
            user=settings.smtp_user,
            password=settings.smtp_password,
            use_tls=settings.smtp_use_tls,
        )
    if kind == "memory":
        return MemoryBackend()
    return ConsoleBackend()
