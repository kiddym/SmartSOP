"""layer_walk 单测——按 backend/tests/fixtures/layer_walk_fixtures.json 跑所有场景。
fixture 与 frontend/tests/fixtures/layerWalkFixtures.json 必须等价。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.layer_walk import LayerRow, compute_layer_updates

FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "layer_walk_fixtures.json"


def _load_fixtures() -> list[dict]:
    return json.loads(FIXTURE_PATH.read_text())["fixtures"]


@pytest.mark.parametrize("fx", _load_fixtures(), ids=lambda fx: fx["name"])
def test_walk_matches_fixture(fx: dict) -> None:
    rows = [
        LayerRow(
            id=r["id"],
            kind=r["kind"],
            level=r["level"],
            has_leaf_children=r["hasLeafChildren"],
        )
        for r in fx["rows"]
    ]
    role_map = fx["roles"]
    actual = compute_layer_updates(rows, role_map)
    assert actual == fx["updates"], (
        f"walk output mismatch for '{fx['name']}':\n"
        f"  expected: {fx['updates']}\n"
        f"  actual:   {actual}"
    )
