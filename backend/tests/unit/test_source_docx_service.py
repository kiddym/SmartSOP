"""P1 源 docx：存储路径 + 模型登记 + 服务存取删。"""

from __future__ import annotations

from pathlib import Path

from app import storage
from app.models import Base


def test_source_docx_path_under_group(storage_tmp: Path) -> None:
    p = storage.source_docx_path("grp-1")
    assert p == storage_tmp / "source_docx" / "grp-1" / "source.docx"


def test_model_registered_in_metadata() -> None:
    assert "tb_procedure_source_docx" in Base.metadata.tables
