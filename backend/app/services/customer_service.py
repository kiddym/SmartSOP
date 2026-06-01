"""客户服务：CRUD（软删）、M:N 备件（全量替换）、列表过滤（part_id 反查）。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.customer import Customer, CustomerPart
from app.schemas.partner import CustomerCreate, CustomerUpdate


def part_ids(db: Session, customer_id: str) -> list[str]:
    return list(
        db.execute(
            select(CustomerPart.part_id)
            .where(CustomerPart.customer_id == customer_id)
            .order_by(CustomerPart.part_id)
        )
        .scalars()
        .all()
    )


def _set_parts(db: Session, customer_id: str, company_id: str, part_id_list: list[str]) -> None:
    for pid in dict.fromkeys(part_id_list):
        db.add(CustomerPart(customer_id=customer_id, part_id=pid, company_id=company_id))


def create_customer(
    db: Session, payload: CustomerCreate, company_id: str, actor_user_id: str | None
) -> Customer:
    c = Customer(
        name=payload.name,
        customer_type=payload.customer_type,
        description=payload.description,
        rate=payload.rate,
        billing_currency=payload.billing_currency,
        address=payload.address,
        phone=payload.phone,
        email=payload.email,
        website=payload.website,
        company_id=company_id,
    )
    db.add(c)
    db.flush()
    _set_parts(db, c.id, company_id, payload.part_ids)
    db.commit()
    db.refresh(c)
    return c


def list_customers(db: Session, *, part_id: str | None = None) -> list[Customer]:
    stmt = select(Customer).where(Customer.is_active.is_(True))
    if part_id is not None:
        stmt = stmt.where(
            Customer.id.in_(select(CustomerPart.customer_id).where(CustomerPart.part_id == part_id))
        )
    return list(db.execute(stmt.order_by(Customer.name, Customer.id)).scalars().all())


def get_customer(db: Session, customer_id: str) -> Customer | None:
    c = db.get(Customer, customer_id)
    if c is None or not c.is_active:
        return None
    return c


def update_customer(
    db: Session, c: Customer, payload: CustomerUpdate, company_id: str, actor_user_id: str | None
) -> Customer:
    data = payload.model_dump(exclude_unset=True)
    new_parts = data.pop("part_ids", None)
    for k, val in data.items():
        setattr(c, k, val)
    if new_parts is not None:
        db.execute(CustomerPart.__table__.delete().where(CustomerPart.customer_id == c.id))
        _set_parts(db, c.id, company_id, new_parts)
    db.commit()
    db.refresh(c)
    return c


def delete_customer(db: Session, c: Customer) -> None:
    c.is_active = False
    c.deleted_at = utcnow()
    db.commit()
