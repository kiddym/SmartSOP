from sqlalchemy import select

from app import tenant
from app.models.company import Company
from app.models.role import Role


def _mk(db, slug):
    c = Company(name=slug, slug=slug)
    db.add(c)
    db.commit()
    return c


def test_auto_stamp_on_insert(db):
    c = _mk(db, "acme")
    token = tenant.set_current_company_id(c.id)
    try:
        r = Role(code="x", name="X", permissions=[])  # no company_id
        db.add(r)
        db.commit()
        db.refresh(r)
        assert r.company_id == c.id
    finally:
        tenant.reset_current_company_id(token)


def test_read_scoped(db):
    c1 = _mk(db, "acme"); c2 = _mk(db, "globex")
    db.add(Role(company_id=c1.id, code="r1", name="R1", permissions=[]))
    db.add(Role(company_id=c2.id, code="r2", name="R2", permissions=[]))
    db.commit()
    token = tenant.set_current_company_id(c1.id)
    try:
        rows = db.execute(select(Role)).scalars().all()
        assert {r.code for r in rows} == {"r1"}
    finally:
        tenant.reset_current_company_id(token)


def test_no_context_no_scope(db):
    c1 = _mk(db, "acme"); c2 = _mk(db, "globex")
    db.add(Role(company_id=c1.id, code="r1", name="R1", permissions=[]))
    db.add(Role(company_id=c2.id, code="r2", name="R2", permissions=[]))
    db.commit()
    # autouse fixture clears context => no scope; login relies on this.
    rows = db.execute(select(Role)).scalars().all()
    assert {r.code for r in rows} == {"r1", "r2"}
