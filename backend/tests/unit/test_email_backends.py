"""EmailBackend 三实现（Phase 5B）。"""
from __future__ import annotations

import pytest

from app.email import get_email_backend, reset_email_backend
from app.email.backends import MemoryBackend


def test_memory_backend_collects():
    b = MemoryBackend()
    b.send("a@x.com", "subj", "body", from_addr="no-reply@x")
    assert b.sent == [("a@x.com", "subj", "body", "no-reply@x")]


def test_factory_memory(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "email_backend", "memory")
    reset_email_backend()
    assert isinstance(get_email_backend(), MemoryBackend)
    reset_email_backend()


def test_factory_console_default(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "email_backend", "console")
    reset_email_backend()
    b = get_email_backend()
    b.send("a@x.com", "s", "b", from_addr="f")  # 不抛即可
    reset_email_backend()


def test_smtp_backend_calls_smtplib(monkeypatch):
    from app.email.backends import SMTPBackend
    sent = {}

    class _FakeSMTP:
        def __init__(self, host, port): sent["addr"] = (host, port)
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): sent["tls"] = True
        def login(self, u, p): sent["login"] = (u, p)
        def send_message(self, msg): sent["msg"] = msg

    monkeypatch.setattr("app.email.backends.smtplib.SMTP", _FakeSMTP)
    SMTPBackend(host="h", port=25, user="u", password="p", use_tls=True).send(
        "a@x.com", "s", "b", from_addr="f@x")
    assert sent["addr"] == ("h", 25)
    assert sent["tls"] is True
    assert sent["login"] == ("u", "p")
