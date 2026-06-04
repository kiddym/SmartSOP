"""公司自查订阅端点：登录即可，返回档位/座席/已解锁功能/三档 catalog。"""

from sqlalchemy import select

from app.models.company import Company


def _admin(client, company="Acme", email="a@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_subscription_default_free(client):
    t = _admin(client)
    r = client.get("/api/v1/billing/subscription", headers=_h(t))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["plan"] == "free"
    assert body["subscription_status"] == "active"
    assert body["seat_used"] == 1  # 注册的 super_admin
    assert body["seat_limit"] == 3
    assert body["features"] == []
    # catalog 含三档
    plans = {e["plan"] for e in body["catalog"]}
    assert plans == {"free", "pro", "enterprise"}
    enterprise = next(e for e in body["catalog"] if e["plan"] == "enterprise")
    assert enterprise["seat_limit"] is None


def test_subscription_reflects_pro(client, db):
    t = _admin(client)
    c = db.execute(select(Company)).scalars().first()
    c.plan = "pro"
    db.commit()
    body = client.get("/api/v1/billing/subscription", headers=_h(t)).json()
    assert body["plan"] == "pro"
    assert body["seat_limit"] == 15
    assert set(body["features"]) == {
        "preventive_maintenance",
        "meters",
        "purchasing",
        "analytics",
        "sop",
    }


def test_subscription_requires_auth(client):
    assert client.get("/api/v1/billing/subscription").status_code == 401
