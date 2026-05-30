"""Minimal i18n: locale resolution + message catalog (Phase 0 ships zh-CN)."""
from __future__ import annotations

from app.config import settings

CATALOG: dict[str, dict[str, str]] = {
    "zh-CN": {
        "auth.invalid_credentials": "邮箱或密码错误",
        "auth.account_disabled": "账号已禁用",
        "auth.email_ambiguous": "该邮箱存在于多个公司，请提供公司标识",
        "auth.company_slug_exists": "公司标识已存在",
        "common.not_found": "资源不存在",
        "common.forbidden": "权限不足",
    },
}


def translate(key: str, locale: str | None = None) -> str:
    loc = locale if locale in CATALOG else settings.default_locale
    return CATALOG.get(loc, {}).get(key, key)


def resolve_locale(user_locale: str | None, accept_language: str | None) -> str:
    if user_locale and user_locale in settings.supported_locales:
        return user_locale
    if accept_language:
        for part in accept_language.split(","):
            code = part.split(";")[0].strip()
            if code in settings.supported_locales:
                return code
    return settings.default_locale
