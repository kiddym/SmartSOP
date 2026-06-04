from app.models.base import TenantScoped
from app.models.folder import Folder
from app.models.procedure import Procedure


def test_sop_models_tenant_scoped():
    assert issubclass(Folder, TenantScoped)
    assert issubclass(Procedure, TenantScoped)
    assert "company_id" in Folder.__table__.columns
    # 多租户硬化后 SOP 表 company_id 收 NOT NULL（fail-closed）。
    assert Folder.__table__.columns["company_id"].nullable is False


def test_folder_auto_stamped_and_scoped(db):
    from sqlalchemy import select

    from app import tenant
    from app.models.company import Company

    c1 = Company(name="c1", slug="c1")
    c2 = Company(name="c2", slug="c2")
    db.add_all([c1, c2])
    db.commit()

    t = tenant.set_current_company_id(c1.id)
    try:
        f = Folder(name="只属于c1", full_path="只属于c1")
        db.add(f)
        db.commit()
        assert f.company_id == c1.id
    finally:
        tenant.reset_current_company_id(t)

    t = tenant.set_current_company_id(c2.id)
    try:
        rows = db.execute(select(Folder)).scalars().all()
        assert rows == []  # c2 sees none of c1's folders
    finally:
        tenant.reset_current_company_id(t)
