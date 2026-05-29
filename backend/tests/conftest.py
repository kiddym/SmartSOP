"""顶层测试 fixtures。

单测用 SQLite in-memory（StaticPool 共享同一连接的内存库），每个 test 用独立
引擎实现隔离。涉及 MySQL 专属行为（生成列 partial-unique）的测试需 MySQL，
本期由 service 层 check-then-act 守卫覆盖等价行为。
"""

from __future__ import annotations

import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
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
    ) -> "ProcedureNode":
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
