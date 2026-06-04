"""顶层测试 fixtures。

单测用 SQLite in-memory（StaticPool 共享同一连接的内存库），每个 test 用独立
引擎实现隔离。涉及 MySQL 专属行为（生成列 partial-unique）的测试需 MySQL，
本期由 service 层 check-then-act 守卫覆盖等价行为。
"""

from __future__ import annotations

import sys
import types
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest

# 让迁移测试可以 `import alembic.versions.<rev>`：把本地迁移目录注册成
# 已安装 alembic 包的 versions 子包（否则 site-packages 的 alembic 会遮蔽本地目录）。
_versions_dir = Path(__file__).resolve().parent.parent / "alembic" / "versions"
if "alembic.versions" not in sys.modules:
    _vpkg = types.ModuleType("alembic.versions")
    _vpkg.__path__ = [str(_versions_dir)]
    sys.modules["alembic.versions"] = _vpkg
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import get_db
from app.main import app
from app.models import (
    Base,
    Folder,
    FolderSequence,
    Procedure,
    ProcedureNode,
    ProcedureSettings,
)


@pytest.fixture
def engine() -> Generator[Engine, None, None]:
    """每个 test 一个全新的内存 SQLite 库。"""
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    try:
        yield eng
    finally:
        Base.metadata.drop_all(eng)
        eng.dispose()


@pytest.fixture
def db(engine: Engine) -> Generator[Session, None, None]:
    """测试数据库 session。"""
    with Session(engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture
def client(engine: Engine) -> Generator[TestClient, None, None]:
    """FastAPI TestClient，get_db 重定向到测试引擎。"""

    def _override_get_db() -> Generator[Session, None, None]:
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class Factory:
    """轻量业务对象工厂，绑定到一个 session。"""

    def __init__(self, session: Session) -> None:
        self.db = session

    def folder(
        self,
        name: str = "测试文件夹",
        prefix: str = "",
        parent_id: str | None = None,
        system: bool = False,
        full_path: str | None = None,
    ) -> Folder:
        folder = Folder(
            name=name,
            prefix=prefix,
            parent_id=parent_id,
            system=system,
            full_path=full_path if full_path is not None else name,
        )
        self.db.add(folder)
        self.db.commit()
        return folder

    def sequence(
        self, folder_id: str, current_value: int = 0, sequence_digits: int = 5
    ) -> FolderSequence:
        seq = FolderSequence(
            folder_id=folder_id,
            current_value=current_value,
            sequence_digits=sequence_digits,
        )
        self.db.add(seq)
        self.db.commit()
        return seq

    def procedure(
        self,
        folder_id: str,
        name: str = "示例程序",
        code: str = "QC-00001",
        level_of_use: str = "reference",
        procedure_group_id: str | None = None,
        version: int = 1,
        status: str = "DRAFT",
        is_current: bool = True,
        **kw: object,
    ) -> Procedure:
        proc = Procedure(
            procedure_group_id=procedure_group_id or str(uuid.uuid4()),
            folder_id=folder_id,
            code=code,
            name=name,
            level_of_use=level_of_use,
            version=version,
            status=status,
            is_current=is_current,
            **kw,
        )
        self.db.add(proc)
        self.db.commit()
        return proc

    def node(
        self,
        procedure_id: str,
        body: str = "",
        sort_order: int = 0,
        heading_level: int | None = None,
        kind: str = "node",
        skip_numbering: bool = False,
        input_schema: dict[str, object] | None = None,
        mark_status: str = "unmarked",
    ) -> ProcedureNode:
        node = ProcedureNode(
            procedure_id=procedure_id,
            body=body,
            sort_order=sort_order,
            heading_level=heading_level,
            kind=kind,
            skip_numbering=skip_numbering,
            input_schema=input_schema if input_schema is not None else {},
            mark_status=mark_status,
        )
        self.db.add(node)
        self.db.commit()
        return node

    def settings(self, **overrides: object) -> ProcedureSettings:
        obj = ProcedureSettings(**overrides)
        self.db.add(obj)
        self.db.commit()
        return obj


@pytest.fixture
def factory(db: Session) -> Factory:
    return Factory(db)


@pytest.fixture
def storage_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Path, None, None]:
    """把 settings.storage_dir 指向临时目录，隔离 asset / 临时上传文件落盘。"""
    root = tmp_path / "storage"
    monkeypatch.setattr(settings, "storage_dir", str(root))
    yield root


@pytest.fixture
def _enterprise_default() -> Generator[None, None, None]:
    """让本测试中新建的公司默认升到 enterprise+active。

    P6 给 meters/pm/purchasing/analytics 挂了 feature gate；这些模块的既有集成测试
    用默认 free 公司直访会变 402。受影响测试文件用
    `pytestmark = pytest.mark.usefixtures("_enterprise_default")` 引用本 fixture 即可整
    文件解锁，无需逐个改注册调用点。需要 free 默认的门控/计费/座席测试不引用本
    fixture，保持显式 free。

    实现走 before_insert 事件显式给实例赋值（而非改列默认）：SQLAlchemy 会把标量
    列默认值烘焙进进程级语句缓存，改 default.arg 撤销后仍会泄漏到后续测试；事件监听
    每次按实例赋值，event.remove 即彻底恢复，无跨测试污染。
    """
    from sqlalchemy import event

    from app.models.company import Company

    def _stamp(_mapper: object, _connection: object, target: Company) -> None:
        target.plan = "enterprise"
        target.subscription_status = "active"

    event.listen(Company, "before_insert", _stamp)
    try:
        yield
    finally:
        event.remove(Company, "before_insert", _stamp)


@pytest.fixture
def _sop_auth(_enterprise_default, client, db):
    """SOP 测试登录态：注册一家 enterprise 公司，默认带 token，并设 tenant 上下文。

    - _enterprise_default（before_insert）确保新公司 enterprise → 解锁 sop。
    - client 默认 header 让无 header 的既有 client 调用自动带 token（测试体不动）。
    - 同步设 tenant 上下文：让用 factory 直接 db.add 的行也被盖对 company_id
      （否则直建行 company_id=NULL，被自动过滤后 API 查不到）。
    """
    from sqlalchemy import select

    from app import tenant
    from app.models.company import Company

    resp = client.post(
        "/api/v1/auth/register",
        json={
            "company_name": "SOPCo",
            "email": "sop@example.com",
            "password": "secret123",
            "name": "Admin",
        },
    )
    token = resp.json()["access_token"]
    company_id = db.execute(select(Company).where(Company.slug == "sopco")).scalar_one().id
    client.headers.update({"Authorization": f"Bearer {token}"})
    ctx = tenant.set_current_company_id(company_id)
    try:
        yield company_id
    finally:
        tenant.reset_current_company_id(ctx)
        client.headers.pop("Authorization", None)


@pytest.fixture(autouse=True)
def _clear_tenant_context():
    """Each test starts/ends with no tenant scope (prevents leakage)."""
    from app import tenant

    tenant.set_current_company_id(None)
    yield
    tenant.set_current_company_id(None)
