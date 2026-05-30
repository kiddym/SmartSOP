from app.config import settings


def test_jwt_settings_present():
    assert settings.secret_key
    assert settings.algorithm == "HS256"
    assert settings.access_token_expire_minutes > 0
    assert settings.refresh_token_expire_days > 0


def test_locale_settings():
    assert settings.default_locale == "zh-CN"
    assert "zh-CN" in settings.supported_locales


def test_app_name_rebranded():
    assert settings.app_name == "Smart CMMS"
