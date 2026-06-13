"""程序列表批量构造的正确性回归（审计 #10：folder_full_path + version_count_in_group）。

采用 `_sop_auth` fixture（enterprise 公司 + 已认证 client）并用本地定义的
`_make_leaf`/`_make_procedure` 助手造一行真实数据，使 path/count 断言真正执行——
而非空 items 的 no-op。验证已填充的行经批量路径（`_out_models`）返回正确的
folder_full_path 与 version_count_in_group。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.usefixtures("_sop_auth")

PROC = "/api/v1/procedures"
FOLDER = "/api/v1/folders"


def _make_leaf(client: TestClient, *, name: str = "叶子", prefix: str = "QC") -> str:
    return client.post(FOLDER, json={"name": name, "prefix": prefix}).json()["id"]


def _make_procedure(client: TestClient, folder_id: str, *, name: str = "启动 SOP") -> dict:
    resp = client.post(
        PROC, json={"folder_id": folder_id, "name": name, "level_of_use": "continuous"}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_library_list_reports_paths_and_counts(client: TestClient) -> None:
    leaf = _make_leaf(client, name="质检", prefix="QC")
    created = _make_procedure(client, leaf, name="批量构造回归")

    r = client.get(PROC, headers=client.headers, params={"page": 1, "page_size": 20})
    assert r.status_code == 200, r.text
    page = r.json()
    assert page["items"], "应至少有一行用于验证 path/count"

    for item in page["items"]:
        assert "folder_full_path" in item
        assert isinstance(item["version_count_in_group"], int)
        assert item["version_count_in_group"] >= 1

    row = next(i for i in page["items"] if i["id"] == created["id"])
    # folder_full_path 须为非空真实路径（_out_models 的 IN() 取值与逐行 db.get 一致）
    assert row["folder_full_path"]
    assert row["version_count_in_group"] == 1
