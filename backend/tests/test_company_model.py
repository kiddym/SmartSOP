from app.models.company import Company, CompanyStatus


def test_company_defaults(db):
    c = Company(name="Acme", slug="acme")
    db.add(c)
    db.commit()
    db.refresh(c)
    assert c.id is not None and len(c.id) == 36
    assert c.status == CompanyStatus.active
    assert c.locale == "zh-CN"
    assert c.is_platform_admin_org is False
