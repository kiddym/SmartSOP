"""numbering_profile_service 单测（P1d）。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.schemas.numbering_profile import NumberingProfileCreate, NumberingProfileUpdate
from app.services import numbering_profile_service as svc


def test_create_and_active_overrides(db) -> None:
    p = svc.create(db, NumberingProfileCreate(pattern_key="第X条", kind="heading", level=3))
    db.flush()
    assert p.source == "manual" and p.status == "active"
    assert svc.active_numbering_overrides(db) == {"第X条": ("heading", 3)}


def test_bad_kind_rejected(db) -> None:
    # 主线 errors.conflict() 返回 HTTPException(409)
    with pytest.raises(HTTPException) as exc:
        svc.create(db, NumberingProfileCreate(pattern_key="X", kind="bogus", level=1))
    assert exc.value.status_code == 409


def test_duplicate_pattern_conflicts(db) -> None:
    svc.create(db, NumberingProfileCreate(pattern_key="N.N、", kind="list", level=None))
    db.flush()
    with pytest.raises(HTTPException) as exc:
        svc.create(db, NumberingProfileCreate(pattern_key="N.N、", kind="heading", level=2))
    assert exc.value.status_code == 409


def test_update_pins_manual_and_bumps_revision(db) -> None:
    p = svc.create(db, NumberingProfileCreate(pattern_key="N、", kind="weak_heading", level=1))
    db.flush()
    before = p.revision
    svc.update(db, p, NumberingProfileUpdate(kind="heading", level=2))
    assert (
        p.kind == "heading" and p.level == 2 and p.source == "manual" and p.revision == before + 1
    )
