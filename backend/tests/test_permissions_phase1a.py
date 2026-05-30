from app import permissions as perms


def test_phase1a_codes_registered():
    for code in [
        "location.view", "location.create", "location.edit", "location.delete",
        "asset.view", "asset.create", "asset.edit", "asset.delete",
        "asset_category.view", "asset_category.manage",
        "team.view", "team.manage",
    ]:
        assert code in perms.ALL_PERMISSIONS


def test_super_admin_wildcard_includes_new_codes():
    assert perms.effective_codes("super_admin", []) == set(perms.ALL_PERMISSIONS)


def test_admin_has_all_phase1a():
    admin = next(r for r in perms.BUILTIN_ROLES if r["code"] == "admin")
    for code in ["location.create", "asset.delete", "asset_category.manage", "team.manage"]:
        assert code in admin["permissions"]


def test_technician_can_edit_asset_not_delete():
    tech = next(r for r in perms.BUILTIN_ROLES if r["code"] == "technician")
    assert "asset.edit" in tech["permissions"]
    assert "asset.delete" not in tech["permissions"]
    assert "location.view" in tech["permissions"]


def test_viewer_only_view():
    viewer = next(r for r in perms.BUILTIN_ROLES if r["code"] == "viewer")
    assert all(c.endswith(".view") for c in viewer["permissions"])
    assert "asset.view" in viewer["permissions"]
