from app import permissions as perms


def test_registry_contains_platform_codes():
    assert "user.create" in perms.ALL_PERMISSIONS
    assert "role.manage" in perms.ALL_PERMISSIONS
    assert "company.settings" in perms.ALL_PERMISSIONS


def test_builtin_roles_present():
    assert {r["code"] for r in perms.BUILTIN_ROLES} == {
        "super_admin", "admin", "technician", "viewer", "requester"}


def test_super_admin_gets_all():
    sa = next(r for r in perms.BUILTIN_ROLES if r["code"] == "super_admin")
    assert set(sa["permissions"]) == set(perms.ALL_PERMISSIONS)


def test_viewer_only_view():
    viewer = next(r for r in perms.BUILTIN_ROLES if r["code"] == "viewer")
    assert all(c.endswith(".view") for c in viewer["permissions"])


def test_effective_codes_super_admin_wildcard():
    assert perms.effective_codes("super_admin", []) == set(perms.ALL_PERMISSIONS)


def test_effective_codes_regular():
    assert perms.effective_codes("admin", ["user.view"]) == {"user.view"}
