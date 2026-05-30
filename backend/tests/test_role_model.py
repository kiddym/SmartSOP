from app.models.company import Company
from app.models.role import Role


def test_role_persists_permissions(db):
    c = Company(name="Acme", slug="acme")
    db.add(c)
    db.commit()
    r = Role(company_id=c.id, code="admin", name="管理员",
             is_builtin=True, permissions=["user.view", "user.create"])
    db.add(r)
    db.commit()
    db.refresh(r)
    assert r.id is not None
    assert r.permissions == ["user.view", "user.create"]
    assert r.is_builtin is True
