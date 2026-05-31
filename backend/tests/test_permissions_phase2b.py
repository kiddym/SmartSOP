from app import permissions as perms


def test_phase2b_codes_registered():
    for code in [
        "preventive_maintenance.view", "preventive_maintenance.create",
        "preventive_maintenance.edit", "preventive_maintenance.delete",
    ]:
        assert code in perms.ALL_PERMISSIONS


def test_super_admin_wildcard_includes_preventive_maintenance():
    assert perms.effective_codes("super_admin", []) == set(perms.ALL_PERMISSIONS)


def test_admin_has_all_preventive_maintenance():
    admin = next(r for r in perms.BUILTIN_ROLES if r["code"] == "admin")
    for code in [
        "preventive_maintenance.view", "preventive_maintenance.create",
        "preventive_maintenance.edit", "preventive_maintenance.delete",
    ]:
        assert code in admin["permissions"]


def test_technician_pm_view_only():
    tech = next(r for r in perms.BUILTIN_ROLES if r["code"] == "technician")
    assert "preventive_maintenance.view" in tech["permissions"]
    assert "preventive_maintenance.create" not in tech["permissions"]
    assert "preventive_maintenance.edit" not in tech["permissions"]
    assert "preventive_maintenance.delete" not in tech["permissions"]


def test_requester_unchanged_no_pm():
    requester = next(r for r in perms.BUILTIN_ROLES if r["code"] == "requester")
    assert set(requester["permissions"]) == {"request.view", "request.create"}


def test_viewer_includes_pm_view():
    viewer = next(r for r in perms.BUILTIN_ROLES if r["code"] == "viewer")
    assert "preventive_maintenance.view" in viewer["permissions"]
    assert "preventive_maintenance.create" not in viewer["permissions"]
    assert all(c.endswith(".view") for c in viewer["permissions"])
