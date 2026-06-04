"""全局设置端点集成测试（api-specification §5.8）。

覆盖：
  - GET /settings 返回 200 + 正确字段
  - GET /settings/current 与 GET /settings 返回相同
  - PUT /settings 无 If-Match → 412
  - PUT /settings 错误 revision → 409
  - PUT /settings 正确 revision → 200 + revision 递增 + 字段更新
  - PUT /settings 字段约束（max_version_number > 9999 → 422，default_risk_level > 5 → 422）
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.settings import ProcedureSettings

pytestmark = pytest.mark.usefixtures("_sop_auth")

SETTINGS = "/api/v1/settings"
SETTINGS_CURRENT = "/api/v1/settings/current"

_DEFAULT_PAYLOAD = {
    "enable_approval_workflow": False,
    "max_version_number": 100,
    "require_read_confirmation": False,
    "default_risk_level": 1,
    "default_quality_level": 1,
}


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def seeded_client(client: TestClient) -> TestClient:
    """_sop_auth 注册时已为本公司播种 settings 单例（seed_tenant_sop），直接复用 client。

    不再手动插入单例：那会与每公司播种的行重复，且在租户上下文下被自动盖上同一
    company_id，导致同公司两条 settings 行让 get_singleton 的 .first() 结果不稳定。
    """
    return client


# --------------------------------------------------------------------------- #
# GET /settings
# --------------------------------------------------------------------------- #


def test_get_settings_200(seeded_client: TestClient) -> None:
    resp = seeded_client.get(SETTINGS)
    assert resp.status_code == 200
    data = resp.json()
    for key in (
        "id",
        "enable_version_control",
        "enable_approval_workflow",
        "max_version_number",
        "require_read_confirmation",
        "default_risk_level",
        "default_quality_level",
        "revision",
        "updated_at",
    ):
        assert key in data, f"missing key: {key}"
    assert data["enable_version_control"] is True
    assert data["revision"] == 0


def test_get_settings_404_when_missing(client: TestClient, db: Session) -> None:
    """删除本公司已播种的 settings 单例后，GET 应返回 404（防御分支）。

    每公司注册即播种 settings，故「未初始化」只能通过显式删除复现。db 在 _sop_auth
    设的租户上下文下，查询只命中本公司的行。
    """
    for s in db.query(ProcedureSettings).all():
        db.delete(s)
    db.commit()
    resp = client.get(SETTINGS)
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "SETTINGS_NOT_FOUND"


def test_get_settings_current_alias(seeded_client: TestClient) -> None:
    """GET /settings/current 与 GET /settings 返回相同数据。"""
    r1 = seeded_client.get(SETTINGS).json()
    r2 = seeded_client.get(SETTINGS_CURRENT).json()
    assert r1 == r2


# --------------------------------------------------------------------------- #
# PUT /settings — 前置检查
# --------------------------------------------------------------------------- #


def test_put_settings_without_if_match_412(seeded_client: TestClient) -> None:
    resp = seeded_client.put(SETTINGS, json=_DEFAULT_PAYLOAD)
    assert resp.status_code == 412
    assert resp.json()["detail"]["code"] == "IF_MATCH_REQUIRED"


def test_put_settings_wrong_revision_409(seeded_client: TestClient) -> None:
    resp = seeded_client.put(
        SETTINGS,
        json=_DEFAULT_PAYLOAD,
        headers={"If-Match": "99"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "VERSION_CONFLICT"


# --------------------------------------------------------------------------- #
# PUT /settings — 正常更新
# --------------------------------------------------------------------------- #


def test_put_settings_success(seeded_client: TestClient) -> None:
    current = seeded_client.get(SETTINGS).json()
    rev = current["revision"]  # 0

    payload = {
        "enable_approval_workflow": True,
        "max_version_number": 50,
        "require_read_confirmation": True,
        "default_risk_level": 3,
        "default_quality_level": 4,
    }
    resp = seeded_client.put(
        SETTINGS,
        json=payload,
        headers={"If-Match": str(rev)},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["enable_approval_workflow"] is True
    assert data["max_version_number"] == 50
    assert data["require_read_confirmation"] is True
    assert data["default_risk_level"] == 3
    assert data["default_quality_level"] == 4
    assert data["revision"] == rev + 1
    # enable_version_control 始终为 true
    assert data["enable_version_control"] is True


def test_put_settings_revision_increments(seeded_client: TestClient) -> None:
    """连续更新两次，revision 累计递增。"""
    r0 = seeded_client.get(SETTINGS).json()["revision"]

    for i in range(2):
        resp = seeded_client.put(
            SETTINGS,
            json=_DEFAULT_PAYLOAD,
            headers={"If-Match": str(r0 + i)},
        )
        assert resp.status_code == 200

    final = seeded_client.get(SETTINGS).json()
    assert final["revision"] == r0 + 2


def test_put_settings_stale_revision_after_update(seeded_client: TestClient) -> None:
    """第一次更新后用旧 revision 再次 PUT 应 409。"""
    rev = seeded_client.get(SETTINGS).json()["revision"]
    # 第一次更新成功
    seeded_client.put(SETTINGS, json=_DEFAULT_PAYLOAD, headers={"If-Match": str(rev)})
    # 用旧 revision 再次更新 → 409
    resp = seeded_client.put(SETTINGS, json=_DEFAULT_PAYLOAD, headers={"If-Match": str(rev)})
    assert resp.status_code == 409


# --------------------------------------------------------------------------- #
# PUT /settings — 字段约束验证
# --------------------------------------------------------------------------- #


def test_put_settings_max_version_number_too_large_422(seeded_client: TestClient) -> None:
    rev = seeded_client.get(SETTINGS).json()["revision"]
    payload = {**_DEFAULT_PAYLOAD, "max_version_number": 10000}
    resp = seeded_client.put(SETTINGS, json=payload, headers={"If-Match": str(rev)})
    assert resp.status_code == 422


def test_put_settings_max_version_number_zero_422(seeded_client: TestClient) -> None:
    rev = seeded_client.get(SETTINGS).json()["revision"]
    payload = {**_DEFAULT_PAYLOAD, "max_version_number": 0}
    resp = seeded_client.put(SETTINGS, json=payload, headers={"If-Match": str(rev)})
    assert resp.status_code == 422


def test_put_settings_risk_level_out_of_range_422(seeded_client: TestClient) -> None:
    rev = seeded_client.get(SETTINGS).json()["revision"]
    payload = {**_DEFAULT_PAYLOAD, "default_risk_level": 6}
    resp = seeded_client.put(SETTINGS, json=payload, headers={"If-Match": str(rev)})
    assert resp.status_code == 422


def test_put_settings_quality_level_out_of_range_422(seeded_client: TestClient) -> None:
    rev = seeded_client.get(SETTINGS).json()["revision"]
    payload = {**_DEFAULT_PAYLOAD, "default_quality_level": 0}
    resp = seeded_client.put(SETTINGS, json=payload, headers={"If-Match": str(rev)})
    assert resp.status_code == 422
