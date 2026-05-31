from app import permissions as perms


def test_phase2c_codes_registered():
    for code in ["meter.view", "meter.create", "meter.edit", "meter.delete",
                 "reading.view", "reading.create"]:
        assert code in perms.ALL_PERMISSIONS


def test_super_admin_wildcard_includes_meter():
    assert perms.effective_codes("super_admin", []) == set(perms.ALL_PERMISSIONS)


def test_admin_has_all_meter():
    admin = next(r for r in perms.BUILTIN_ROLES if r["code"] == "admin")
    for code in ["meter.view", "meter.create", "meter.edit", "meter.delete",
                 "reading.view", "reading.create"]:
        assert code in admin["permissions"]


def test_technician_meter_view_and_reading_rw():
    tech = next(r for r in perms.BUILTIN_ROLES if r["code"] == "technician")
    assert "meter.view" in tech["permissions"]
    assert "reading.view" in tech["permissions"]
    assert "reading.create" in tech["permissions"]
    assert "meter.create" not in tech["permissions"]
    assert "meter.edit" not in tech["permissions"]
    assert "meter.delete" not in tech["permissions"]


def test_requester_unchanged_no_meter():
    requester = next(r for r in perms.BUILTIN_ROLES if r["code"] == "requester")
    assert set(requester["permissions"]) == {"request.view", "request.create"}


def test_viewer_includes_meter_view_and_reading_view():
    viewer = next(r for r in perms.BUILTIN_ROLES if r["code"] == "viewer")
    assert "meter.view" in viewer["permissions"]
    assert "reading.view" in viewer["permissions"]
    assert "meter.create" not in viewer["permissions"]
    assert "reading.create" not in viewer["permissions"]
    assert all(c.endswith(".view") for c in viewer["permissions"])
