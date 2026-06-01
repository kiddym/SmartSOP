"""Phase 5B 配置项默认值（开箱即用、测试零网络）。"""
from __future__ import annotations

from app.config import settings


def test_email_defaults():
    assert settings.email_backend == "console"
    assert settings.email_from == "no-reply@smart-cmms.local"
    assert settings.email_max_attempts == 5
    assert settings.smtp_port == 587
    assert settings.smtp_use_tls is True


def test_storage_defaults():
    assert settings.storage_backend == "local"
    assert settings.s3_bucket == ""
    assert settings.s3_endpoint_url == ""
