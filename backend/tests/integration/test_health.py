"""健康检查与 request-id 中间件集成测试。"""

from __future__ import annotations

import pytest
from sqlalchemy import Engine


def test_healthz_returns_ok(client) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_readyz_ok_when_db_reachable(
    client, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.main.engine", engine)
    resp = client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json()["db"] == "up"


def test_readyz_503_when_db_down(client, monkeypatch: pytest.MonkeyPatch) -> None:
    from sqlalchemy import create_engine

    broken = create_engine("sqlite:///file:nonexistent?mode=ro&uri=true")
    monkeypatch.setattr("app.main.engine", broken)
    resp = client.get("/readyz")
    assert resp.status_code == 503
    assert resp.json()["db"] == "down"


def test_readyz_reports_soffice_up(client, engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.main.engine", engine)
    monkeypatch.setattr("app.main.images.soffice_available", lambda: True)
    resp = client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json()["soffice"] == "up"


def test_readyz_reports_soffice_down_but_still_200(
    client, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.main.engine", engine)
    monkeypatch.setattr("app.main.images.soffice_available", lambda: False)
    resp = client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json()["soffice"] == "down"


def test_probe_soffice_warns_when_missing(monkeypatch: pytest.MonkeyPatch, caplog) -> None:
    import logging

    from app import main as main_mod

    monkeypatch.setattr(main_mod.images, "soffice_available", lambda: False)
    with caplog.at_level(logging.WARNING):
        main_mod._probe_soffice()
    assert any(
        ("soffice" in r.message.lower()) or ("LibreOffice" in r.message) for r in caplog.records
    )


def test_request_id_echoed_when_provided(client) -> None:
    resp = client.get("/healthz", headers={"X-Request-Id": "abc-123"})
    assert resp.headers["x-request-id"] == "abc-123"


def test_request_id_generated_when_absent(client) -> None:
    resp = client.get("/healthz")
    assert resp.headers.get("x-request-id")
