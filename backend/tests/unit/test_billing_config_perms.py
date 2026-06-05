from app import permissions
from app.config import settings


def test_billing_config_fields_default_empty():
    assert settings.stripe_secret_key == ""
    assert settings.stripe_price_pro == ""
    assert settings.billing_portal_return_url.startswith("http")


def test_billing_manage_permission_registered():
    assert permissions.BILLING_MANAGE == "billing.manage"
    assert permissions.BILLING_MANAGE in permissions.ALL_PERMISSIONS
    admin = next(r for r in permissions.BUILTIN_ROLES if r["code"] == "admin")
    assert permissions.BILLING_MANAGE in admin["permissions"]
