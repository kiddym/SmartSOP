from app import i18n


def test_translate_known_zh():
    assert i18n.translate("auth.invalid_credentials", "zh-CN") == "邮箱或密码错误"


def test_translate_unknown_returns_key():
    assert i18n.translate("nope.nope", "zh-CN") == "nope.nope"


def test_resolve_locale_priority():
    assert i18n.resolve_locale(user_locale="zh-CN", accept_language="en") == "zh-CN"
    assert i18n.resolve_locale(user_locale=None, accept_language="zh-CN,en;q=0.9") == "zh-CN"
    assert i18n.resolve_locale(user_locale=None, accept_language="fr") == "zh-CN"
