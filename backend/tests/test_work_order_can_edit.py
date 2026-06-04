from app import tenant
from app.models.company import Company
from app.models.role import Role
from app.models.user import User
from app.models.work_order import WorkOrder, WorkOrderAssignee
from app.models.work_order_status import WorkOrderStatus
from app.services import work_order_service as svc


def _setup(db, role_code, status=WorkOrderStatus.IN_PROGRESS, created_by="creator"):
    c = Company(name="Acme", slug="acme")
    db.add(c)
    db.commit()
    tenant.set_current_company_id(c.id)
    role = Role(code=role_code, name=role_code, company_id=c.id, permissions=[])
    db.add(role)
    db.commit()
    wo = WorkOrder(
        custom_id="WO000001",
        title="t",
        company_id=c.id,
        status=status,
        created_by_user_id=created_by,
    )
    db.add(wo)
    db.commit()
    return c, role, wo


def _user(db, uid, role_id, company_id):
    u = User(
        id=uid,
        email=f"{uid}@a.com",
        password_hash="x",
        name=uid,
        role_id=role_id,
        company_id=company_id,
    )
    db.add(u)
    db.commit()
    return u


def test_admin_can_edit_even_in_terminal(db):
    c, role, wo = _setup(db, "admin", status=WorkOrderStatus.COMPLETE, created_by="other")
    u = _user(db, "adm", role.id, c.id)
    assert svc.can_edit_work_order(db, u, wo) is True


def test_terminal_locks_non_admin(db):
    c, role, wo = _setup(db, "technician", status=WorkOrderStatus.COMPLETE, created_by="creator")
    u = _user(db, "creator", role.id, c.id)
    assert svc.can_edit_work_order(db, u, wo) is False


def test_creator_can_edit_non_terminal(db):
    c, role, wo = _setup(db, "technician", created_by="creator")
    u = _user(db, "creator", role.id, c.id)
    assert svc.can_edit_work_order(db, u, wo) is True


def test_assignee_can_edit(db):
    c, role, wo = _setup(db, "technician", created_by="other")
    u = _user(db, "asg", role.id, c.id)
    db.add(WorkOrderAssignee(work_order_id=wo.id, user_id="asg", company_id=c.id))
    db.commit()
    assert svc.can_edit_work_order(db, u, wo) is True


def test_unrelated_user_cannot_edit(db):
    c, role, wo = _setup(db, "technician", created_by="other")
    u = _user(db, "stranger", role.id, c.id)
    assert svc.can_edit_work_order(db, u, wo) is False


def test_patch_returns_403_when_predicate_false(client, monkeypatch):
    from app.services import work_order_service

    t = client.post(
        "/api/v1/auth/register",
        json={"company_name": "Acme", "email": "a@a.com", "password": "secret123", "name": "A"},
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    wid = client.post("/api/v1/work-orders", headers=h, json={"title": "t"}).json()["id"]
    monkeypatch.setattr(work_order_service, "can_edit_work_order", lambda *a, **k: False)
    r = client.patch(f"/api/v1/work-orders/{wid}", headers=h, json={"title": "x"})
    assert r.status_code == 403, r.text


def test_read_exposes_can_be_edited(client):
    t = client.post(
        "/api/v1/auth/register",
        json={"company_name": "Acme", "email": "a@a.com", "password": "secret123", "name": "A"},
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    wo = client.post("/api/v1/work-orders", headers=h, json={"title": "t"}).json()
    assert wo["can_be_edited"] is True
