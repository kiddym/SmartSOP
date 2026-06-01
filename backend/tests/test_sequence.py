from app.models.company import Company
from app.services import sequence_service


def _company(db, slug):
    c = Company(name=slug, slug=slug)
    db.add(c)
    db.commit()
    return c


def test_next_value_starts_at_one_and_increments(db):
    c = _company(db, "acme")
    assert sequence_service.next_value(db, "asset", c.id) == 1
    assert sequence_service.next_value(db, "asset", c.id) == 2
    assert sequence_service.next_value(db, "asset", c.id) == 3


def test_scopes_are_independent(db):
    c = _company(db, "acme")
    assert sequence_service.next_value(db, "asset", c.id) == 1
    assert sequence_service.next_value(db, "location", c.id) == 1
    assert sequence_service.next_value(db, "asset", c.id) == 2


def test_tenants_are_independent(db):
    c1 = _company(db, "acme")
    c2 = _company(db, "globex")
    assert sequence_service.next_value(db, "asset", c1.id) == 1
    assert sequence_service.next_value(db, "asset", c1.id) == 2
    assert sequence_service.next_value(db, "asset", c2.id) == 1  # 独立计数


def test_format_custom_id():
    assert sequence_service.format_custom_id("A", 1) == "A000001"
    assert sequence_service.format_custom_id("L", 42) == "L000042"
