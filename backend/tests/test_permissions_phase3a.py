from app import permissions as perms


def test_phase3a_codes_registered():
    for code in ["part.view", "part.create", "part.edit", "part.delete",
                 "part.consume", "part_category.view", "part_category.manage"]:
        assert code in perms.ALL_PERMISSIONS


def test_super_admin_wildcard_includes_part():
    assert perms.effective_codes("super_admin", []) == set(perms.ALL_PERMISSIONS)


def test_admin_has_all_part():
    admin = next(r for r in perms.BUILTIN_ROLES if r["code"] == "admin")
    for code in ["part.view", "part.create", "part.edit", "part.delete",
                 "part.consume", "part_category.view", "part_category.manage"]:
        assert code in admin["permissions"]


def test_technician_part_view_consume_category_view():
    tech = next(r for r in perms.BUILTIN_ROLES if r["code"] == "technician")
    assert "part.view" in tech["permissions"]
    assert "part.consume" in tech["permissions"]
    assert "part_category.view" in tech["permissions"]
    assert "part.create" not in tech["permissions"]
    assert "part.edit" not in tech["permissions"]
    assert "part.delete" not in tech["permissions"]
    assert "part_category.manage" not in tech["permissions"]


def test_requester_unchanged_no_part():
    requester = next(r for r in perms.BUILTIN_ROLES if r["code"] == "requester")
    assert set(requester["permissions"]) == {"request.view", "request.create"}


def test_viewer_includes_part_view_and_category_view():
    viewer = next(r for r in perms.BUILTIN_ROLES if r["code"] == "viewer")
    assert "part.view" in viewer["permissions"]
    assert "part_category.view" in viewer["permissions"]
    assert "part.consume" not in viewer["permissions"]
    assert "part.create" not in viewer["permissions"]
    assert all(c.endswith(".view") for c in viewer["permissions"])
