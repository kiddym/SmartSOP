from app import permissions as perms


def test_phase1b_codes_registered():
    for code in [
        "work_order.view", "work_order.create", "work_order.edit",
        "work_order.delete", "work_order.execute",
    ]:
        assert code in perms.ALL_PERMISSIONS


def test_super_admin_wildcard_includes_workorder():
    assert perms.effective_codes("super_admin", []) == set(perms.ALL_PERMISSIONS)


def test_admin_has_all_workorder():
    admin = next(r for r in perms.BUILTIN_ROLES if r["code"] == "admin")
    for code in ["work_order.create", "work_order.delete", "work_order.execute"]:
        assert code in admin["permissions"]


def test_technician_workorder_view_execute_edit_not_delete():
    tech = next(r for r in perms.BUILTIN_ROLES if r["code"] == "technician")
    assert "work_order.view" in tech["permissions"]
    assert "work_order.execute" in tech["permissions"]
    assert "work_order.edit" in tech["permissions"]
    assert "work_order.create" not in tech["permissions"]
    assert "work_order.delete" not in tech["permissions"]


def test_viewer_only_view():
    viewer = next(r for r in perms.BUILTIN_ROLES if r["code"] == "viewer")
    assert "work_order.view" in viewer["permissions"]
    assert "work_order.execute" not in viewer["permissions"]
    assert all(c.endswith(".view") for c in viewer["permissions"])
