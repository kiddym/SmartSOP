from app import permissions as perms


def test_phase2a_codes_registered():
    for code in [
        "request.view", "request.create", "request.cancel",
        "request.delete", "request.approve",
    ]:
        assert code in perms.ALL_PERMISSIONS


def test_super_admin_wildcard_includes_request():
    assert perms.effective_codes("super_admin", []) == set(perms.ALL_PERMISSIONS)


def test_admin_has_all_request():
    admin = next(r for r in perms.BUILTIN_ROLES if r["code"] == "admin")
    for code in ["request.create", "request.approve", "request.delete"]:
        assert code in admin["permissions"]


def test_technician_request_view_create_not_approve():
    tech = next(r for r in perms.BUILTIN_ROLES if r["code"] == "technician")
    assert "request.view" in tech["permissions"]
    assert "request.create" in tech["permissions"]
    assert "request.approve" not in tech["permissions"]


def test_requester_role_exists_view_create_only():
    requester = next(r for r in perms.BUILTIN_ROLES if r["code"] == "requester")
    assert set(requester["permissions"]) == {"request.view", "request.create"}


def test_viewer_includes_request_view():
    viewer = next(r for r in perms.BUILTIN_ROLES if r["code"] == "viewer")
    assert "request.view" in viewer["permissions"]
    assert "request.approve" not in viewer["permissions"]
    assert all(c.endswith(".view") for c in viewer["permissions"])
