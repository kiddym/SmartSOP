from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.role import Role
from app.models.user import User, UserStatus
from app.schemas.request import RequestCreate
from app.services import request_service as reqs

CO = "co-1"


def _approver(db, code_perm):
    db.add(Role(id=f"r-{code_perm}", code="appr", name="A", permissions=[code_perm], company_id=CO))
    db.commit()
    db.add(
        User(
            id="appr",
            email="appr@x.com",
            password_hash="x",
            name="appr",
            status=UserStatus.active,
            role_id=f"r-{code_perm}",
            company_id=CO,
        )
    )
    db.commit()


def test_create_request_notifies_approvers(db: Session):
    _approver(db, "request.approve")
    reqs.create_request(db, RequestCreate(title="申请X"), CO, actor_user_id=None)
    row = (
        db.execute(select(Notification).where(Notification.type == "REQUEST_SUBMITTED"))
        .scalars()
        .one()
    )
    assert row.recipient_user_id == "appr" and row.entity_type == "request"
