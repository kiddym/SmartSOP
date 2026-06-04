"""sequence_generator 单测（testing-standards §6.1）。"""

from __future__ import annotations

import logging

import pytest
from fastapi import HTTPException

from app.services import sequence_generator
from tests.conftest import Factory

pytestmark = pytest.mark.usefixtures("_tenant_ctx")


def test_next_value_increments_and_zero_pads(db, factory: Factory) -> None:
    """连续生成自增并按 sequence_digits 补零。"""
    folder = factory.folder(name="质检", prefix="QC")
    factory.sequence(folder.id, current_value=0, sequence_digits=5)

    assert sequence_generator.next_sequence_value(db, folder.id) == "00001"
    db.commit()
    assert sequence_generator.next_sequence_value(db, folder.id) == "00002"


def test_sequential_generation_has_no_duplicates(db, factory: Factory) -> None:
    """同 folder 连续生成 10 次结果无重复。"""
    folder = factory.folder(prefix="QC")
    factory.sequence(folder.id, sequence_digits=4)

    values = set()
    for _ in range(10):
        values.add(sequence_generator.next_sequence_value(db, folder.id))
        db.commit()

    assert len(values) == 10


def test_overflow_resets_to_one_and_warns(db, factory: Factory, caplog) -> None:
    """达到 9999（4 位）后下一个返回 0001 且记 WARN（data-model §3.2）。"""
    folder = factory.folder(prefix="QC")
    factory.sequence(folder.id, current_value=9999, sequence_digits=4)

    with caplog.at_level(logging.WARNING):
        result = sequence_generator.next_sequence_value(db, folder.id)

    assert result == "0001"
    assert any("overflow" in r.message.lower() for r in caplog.records)


def test_missing_sequence_raises_404(db, factory: Factory) -> None:
    """无 folder_sequence 记录（非叶子）时抛 404。"""
    folder = factory.folder(prefix="QC")  # 未建 sequence

    with pytest.raises(HTTPException) as exc:
        sequence_generator.next_sequence_value(db, folder.id)

    assert exc.value.status_code == 404
    assert exc.value.detail["code"] == "FOLDER_SEQUENCE_NOT_FOUND"
