from app import permissions as perms


def test_phase3c_codes_registered():
    for code in [
        "purchase_order.view",
        "purchase_order.create",
        "purchase_order.edit",
        "purchase_order.delete",
        "purchase_order.approve",
    ]:
        assert code in perms.ALL_PERMISSIONS


def test_no_duplicate_codes():
    assert len(perms.ALL_PERMISSIONS) == len(set(perms.ALL_PERMISSIONS))


def test_super_admin_wildcard_includes_po():
    assert perms.effective_codes("super_admin", []) == set(perms.ALL_PERMISSIONS)


def test_admin_has_all_po():
    admin = next(r for r in perms.BUILTIN_ROLES if r["code"] == "admin")
    for code in [
        "purchase_order.view",
        "purchase_order.create",
        "purchase_order.edit",
        "purchase_order.delete",
        "purchase_order.approve",
    ]:
        assert code in admin["permissions"]


def test_technician_po_view_only():
    tech = next(r for r in perms.BUILTIN_ROLES if r["code"] == "technician")
    assert "purchase_order.view" in tech["permissions"]
    for denied in (
        "purchase_order.create",
        "purchase_order.edit",
        "purchase_order.delete",
        "purchase_order.approve",
    ):
        assert denied not in tech["permissions"]


def test_requester_unchanged():
    requester = next(r for r in perms.BUILTIN_ROLES if r["code"] == "requester")
    assert set(requester["permissions"]) == {"request.view", "request.create"}


def test_viewer_includes_po_view_only():
    viewer = next(r for r in perms.BUILTIN_ROLES if r["code"] == "viewer")
    assert "purchase_order.view" in viewer["permissions"]
    assert "purchase_order.approve" not in viewer["permissions"]
    assert all(c.endswith(".view") for c in viewer["permissions"])
