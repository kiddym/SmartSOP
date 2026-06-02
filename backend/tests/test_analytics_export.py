"""分析 CSV 导出（Phase 4）。"""

from __future__ import annotations


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _admin(client, *, company="Acme", email="admin@acme.com"):
    return client.post(
        "/api/v1/auth/register",
        json={"company_name": company, "email": email, "password": "secret123", "name": "Admin"},
    ).json()["access_token"]


def test_export_csv_content_type_and_header(client):
    t = _admin(client)
    r = client.get("/api/v1/analytics/work-orders/export", headers=_h(t))
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    first_line = r.text.splitlines()[0]
    assert first_line == "status,count,pct"


def test_export_rows_match_breakdown(client):
    t = _admin(client)
    r = client.get("/api/v1/analytics/work-orders/export", headers=_h(t))
    # 工单盘按 5 个状态各一行 + 表头
    lines = [ln for ln in r.text.splitlines() if ln.strip()]
    assert len(lines) == 1 + 5


def test_export_all_dashboards_csv(client):
    t = _admin(client)
    expected_headers = {
        "work-orders": "status,count,pct",
        "costs": "part_id,custom_id,name,qty,cost",
        "asset-reliability": "asset_id,custom_id,name,availability_pct,downtime_count,total_downtime_hours,mttr_hours,mtbf_hours",
        "inventory": "custom_id,name,category,quantity,min_quantity,cost,value,is_low_stock",
    }
    for dash, header in expected_headers.items():
        r = client.get(f"/api/v1/analytics/{dash}/export", headers=_h(t))
        assert r.status_code == 200, (dash, r.text)
        assert r.text.splitlines()[0] == header


def test_export_new_dashboards(client):
    t = _admin(client)
    for path in ("requests", "personnel", "trends"):
        r = client.get(f"/api/v1/analytics/{path}/export", headers=_h(t))
        assert r.status_code == 200, (path, r.text)
        assert r.headers["content-type"].startswith("text/csv")


def test_export_invalid_dashboard_404(client):
    t = _admin(client)
    assert client.get("/api/v1/analytics/nope/export", headers=_h(t)).status_code == 404


def test_export_requires_permission(client):
    assert client.get("/api/v1/analytics/work-orders/export").status_code == 401
