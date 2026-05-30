from sqlalchemy import MetaData, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.models.base import NAMING_CONVENTION, TenantScoped, TenantMixin, NullableTenantMixin, UUIDMixin


class _TestBase(DeclarativeBase):
    """Isolated declarative base for mixin unit tests; keeps _strict_tenant /
    _loose_tenant out of the shared Base.metadata so that conftest create_all
    (which runs before tb_company exists) does not fail on unresolvable FKs."""
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class _Strict(_TestBase, UUIDMixin, TenantMixin):
    __tablename__ = "_strict_tenant"
    name: Mapped[str] = mapped_column(String(50))


class _Loose(_TestBase, UUIDMixin, NullableTenantMixin):
    __tablename__ = "_loose_tenant"
    name: Mapped[str] = mapped_column(String(50))


def test_strict_not_null_and_scoped():
    assert issubclass(_Strict, TenantScoped)
    assert _Strict.__table__.columns["company_id"].nullable is False


def test_loose_nullable_and_scoped():
    assert issubclass(_Loose, TenantScoped)
    assert _Loose.__table__.columns["company_id"].nullable is True
