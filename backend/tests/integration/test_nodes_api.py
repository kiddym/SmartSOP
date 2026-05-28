"""节点 API 集成测试。

`factory` 与 `client` fixture 共用同一个 in-memory engine(conftest:StaticPool),
故 factory 落库的数据对 client 请求可见。沿用仓库既有 integration 测试的 fixture 用法。
"""

from __future__ import annotations

from tests.conftest import Factory


def _proc(factory: Factory):
    folder = factory.folder()
    return factory.procedure(folder_id=folder.id)


def test_get_nodes_endpoint(client, factory: Factory) -> None:
    proc = _proc(factory)
    factory.node(proc.id, body="<p>A</p>", sort_order=10, heading_level=1)
    resp = client.get(f"/api/v1/procedures/{proc.id}/nodes")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1 and data[0]["heading_level"] == 1 and data[0]["parent_id"] is None


def test_patch_promote_endpoint(client, factory: Factory) -> None:
    proc = _proc(factory)
    n = factory.node(proc.id, body="<p>3.1 X</p>", sort_order=10, heading_level=None)
    resp = client.patch(
        f"/api/v1/nodes/{n.id}",
        json={"heading_level": 2, "set_heading_level": True},
        headers={"If-Match": "1"},
    )
    assert resp.status_code == 200
    assert resp.json()["heading_level"] == 2


def test_patch_requires_if_match(client, factory: Factory) -> None:
    proc = _proc(factory)
    n = factory.node(proc.id, body="<p>A</p>", sort_order=10, heading_level=None)
    resp = client.patch(
        f"/api/v1/nodes/{n.id}", json={"heading_level": 2, "set_heading_level": True}
    )
    assert resp.status_code == 412


def test_batch_endpoint(client, factory: Factory) -> None:
    proc = _proc(factory)
    a = factory.node(proc.id, body="<p>a</p>", sort_order=10, heading_level=None)
    b = factory.node(proc.id, body="<p>b</p>", sort_order=20, heading_level=None)
    resp = client.patch(
        f"/api/v1/procedures/{proc.id}/nodes:batch",
        json={"updates": {
            a.id: {"heading_level": 3, "set_heading_level": True},
            b.id: {"heading_level": 3, "set_heading_level": True},
        }},
    )
    assert resp.status_code == 200
