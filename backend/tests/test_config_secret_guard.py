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
    secret = "a-strong-random-secret-value-1234567890"
    s = Settings(app_env="production", secret_key=secret, _env_file=None)
    assert s.is_production and s.secret_key == secret


def test_blank_secret_rejected_in_production():
    with pytest.raises(ValidationError):
        Settings(app_env="production", secret_key="   ", _env_file=None)


def test_short_secret_rejected_in_production():
    with pytest.raises(ValidationError):
        Settings(app_env="production", secret_key="too-short", _env_file=None)


def test_strong_secret_ok_in_production():
    strong = "x" * 32
    s = Settings(app_env="production", secret_key=strong, _env_file=None)
    assert s.is_production and s.secret_key == strong


def test_short_secret_ok_in_development():
    # dev is unaffected by the strength requirement
    s = Settings(app_env="development", secret_key="short", _env_file=None)
    assert s.secret_key == "short"
