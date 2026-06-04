"""座席上限：满员拒新邀请(402)；降档超员保留存量、仅拦新增。

座席占用 = 在职用户(active) + 待处理邀请(pending)；待处理邀请预占一席，否则可
无限发邀请绕过上限。
"""

from sqlalchemy import select

from app.models.company import Company


def _admin(client, company="Acme", email="a@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _invite(client, t, email):
    return client.post("/api/v1/users/invite", headers=_h(t), json={"email": email})


def test_free_seat_limit_blocks_third_invite(client):
    # free 上限 3；注册占 1 席，可再邀 2 个，第 3 个被拒
    t = _admin(client)
    assert _invite(client, t, "u1@acme.com").status_code == 201
    assert _invite(client, t, "u2@acme.com").status_code == 201
    r = _invite(client, t, "u3@acme.com")
    assert r.status_code == 402, r.text
    assert r.json()["detail"]["code"] == "SEAT_LIMIT_REACHED"


def test_pro_allows_more_seats(client, db):
    t = _admin(client)
    c = db.execute(select(Company)).scalars().first()
    c.plan = "pro"  # 上限 15
    db.commit()
    for i in range(5):
        assert _invite(client, t, f"u{i}@acme.com").status_code == 201


def test_expired_pending_invite_does_not_occupy_seat(client, db):
    # free 上限 3：注册占 1 席 + 2 待处理 = 满；第三邀被拒。让一封邀请过期后应释放该席。
    from datetime import timedelta

    from app.models.base import utcnow
    from app.models.user_invitation import UserInvitation

    t = _admin(client)
    assert _invite(client, t, "u1@acme.com").status_code == 201
    assert _invite(client, t, "u2@acme.com").status_code == 201
    assert _invite(client, t, "u3@acme.com").status_code == 402

    inv = db.execute(
        select(UserInvitation).where(UserInvitation.email == "u1@acme.com")
    ).scalar_one()
    inv.expires_at = utcnow() - timedelta(days=1)
    db.commit()

    # 过期邀请不可被接受、亦不应继续占席 → 可再邀
    assert _invite(client, t, "u3@acme.com").status_code == 201, "过期邀请不应占用席位"


def test_downgrade_keeps_existing_blocks_new(client, db):
    # pro 下邀满 4 人（1 在职 + 4 待处理 = 5 席），再降回 free（上限3），存量保留但新邀被拒
    t = _admin(client)
    c = db.execute(select(Company)).scalars().first()
    c.plan = "pro"
    db.commit()
    for i in range(4):
        assert _invite(client, t, f"u{i}@acme.com").status_code == 201
    c = db.execute(select(Company)).scalars().first()
    c.plan = "free"
    db.commit()
    r = _invite(client, t, "extra@acme.com")
    assert r.status_code == 402, r.text
