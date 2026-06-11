"""生产环境必须显式配置 SECRET_KEY（审计 #3）。"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings

_DEFAULT = "dev-insecure-change-me"


def test_default_secret_rejected_in_production():
    with pytest.raises(ValidationError):
        Settings(app_env="production", secret_key=_DEFAULT, _env_file=None)


def test_default_secret_ok_in_development():
    s = Settings(app_env="development", secret_key=_DEFAULT, _env_file=None)
    assert s.secret_key == _DEFAULT


def test_explicit_secret_ok_in_production():
    s = Settings(app_env="production", secret_key="a-strong-random-secret", _env_file=None)
    assert s.is_production and s.secret_key == "a-strong-random-secret"
