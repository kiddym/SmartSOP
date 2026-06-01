from app import permissions as perms


def test_phase3b_codes_registered():
    for code in [
        "vendor.view",
        "vendor.create",
        "vendor.edit",
        "vendor.delete",
        "customer.view",
        "customer.create",
        "customer.edit",
        "customer.delete",
        "cost_category.view",
        "cost_category.manage",
    ]:
        assert code in perms.ALL_PERMISSIONS


def test_super_admin_wildcard_includes_partner():
    assert perms.effective_codes("super_admin", []) == set(perms.ALL_PERMISSIONS)


def test_admin_has_all_partner():
    admin = next(r for r in perms.BUILTIN_ROLES if r["code"] == "admin")
    for code in [
        "vendor.view",
        "vendor.create",
        "vendor.edit",
        "vendor.delete",
        "customer.view",
        "customer.create",
        "customer.edit",
        "customer.delete",
        "cost_category.view",
        "cost_category.manage",
    ]:
        assert code in admin["permissions"]


def test_technician_partner_view_only():
    tech = next(r for r in perms.BUILTIN_ROLES if r["code"] == "technician")
    assert "vendor.view" in tech["permissions"]
    assert "customer.view" in tech["permissions"]
    assert "cost_category.view" in tech["permissions"]
    for denied in (
        "vendor.create",
        "vendor.edit",
        "vendor.delete",
        "customer.create",
        "customer.edit",
        "customer.delete",
        "cost_category.manage",
    ):
        assert denied not in tech["permissions"]


def test_requester_unchanged_no_partner():
    requester = next(r for r in perms.BUILTIN_ROLES if r["code"] == "requester")
    assert set(requester["permissions"]) == {"request.view", "request.create"}


def test_viewer_includes_partner_views():
    viewer = next(r for r in perms.BUILTIN_ROLES if r["code"] == "viewer")
    assert "vendor.view" in viewer["permissions"]
    assert "customer.view" in viewer["permissions"]
    assert "cost_category.view" in viewer["permissions"]
    assert "vendor.create" not in viewer["permissions"]
    assert all(c.endswith(".view") for c in viewer["permissions"])
