"""动态标题字典-样式规则端点集成测试（方案 M1）。

覆盖：创建（201）/ 列表 / 更新 level·status / 软删（204）/ 重复名冲突 / 404。
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from tests.unit.parser._docx_builder import DocxBuilder

RULES = "/api/v1/heading-rules"
UPLOADS = "/api/v1/uploads"
PARSE = "/api/v1/parse"
IMPORT = "/api/v1/procedures/import"
FOLDER = "/api/v1/folders"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _titles(chapters: list[dict]) -> list[str]:
    out: list[str] = []
    for c in chapters:
        if c["content_type"] == "chapter":
            out.append(c["title"])
        out.extend(_titles(c["children"]))
    return out


def _parse_custom(client: TestClient, name: str = "公司专用标题样式") -> list[dict]:
    # 含一个标准 Heading1（保证 parse 成功），外加一个自定义样式段「范围」作被测对象。
    data = (
        DocxBuilder()
        .heading("目的", level=1)
        .para("本程序的目的。")
        .styled_heading("范围", name)
        .para("适用于全公司。")
        .build()
    )
    token = client.post(UPLOADS, files={"file": ("a.docx", data, DOCX_MIME)}).json()[
        "upload_token"
    ]
    resp = client.post(PARSE, json={"upload_token": token, "parse_mode": "smart"})
    assert resp.status_code == 200, resp.text
    return resp.json()["chapters"]


def test_crud_flow(client: TestClient) -> None:
    # 创建
    resp = client.post(RULES, json={"style_name": "公司章标题", "level": 1})
    assert resp.status_code == 201, resp.text
    rule = resp.json()
    assert rule["style_name"] == "公司章标题"
    assert rule["level"] == 1
    assert rule["source"] == "manual"
    assert rule["status"] == "active"
    rule_id = rule["id"]

    # 列表
    resp = client.get(RULES)
    assert resp.status_code == 200
    assert any(r["id"] == rule_id for r in resp.json())

    # 更新 level + status
    resp = client.put(f"{RULES}/{rule_id}", json={"level": 2, "status": "candidate"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["level"] == 2
    assert resp.json()["status"] == "candidate"

    # 软删
    resp = client.delete(f"{RULES}/{rule_id}")
    assert resp.status_code == 204
    resp = client.get(RULES)
    assert all(r["id"] != rule_id for r in resp.json())


def test_duplicate_name_conflict(client: TestClient) -> None:
    assert client.post(RULES, json={"style_name": "同名样式", "level": 1}).status_code == 201
    resp = client.post(RULES, json={"style_name": "同名样式", "level": 2})
    assert resp.status_code == 409, resp.text


def test_update_missing_404(client: TestClient) -> None:
    resp = client.put(f"{RULES}/nonexistent-id", json={"level": 1})
    assert resp.status_code == 404


def test_level_zero_normalized_to_null(client: TestClient) -> None:
    # level=0（「非标题」）应归一为 null
    resp = client.post(RULES, json={"style_name": "非标题样式", "level": 0})
    assert resp.status_code == 201, resp.text
    assert resp.json()["level"] is None


PROFILES = "/api/v1/numbering-profiles"


def test_numbering_profile_crud(client: TestClient) -> None:
    resp = client.post(PROFILES, json={"pattern_key": "第X条", "kind": "heading", "level": 3})
    assert resp.status_code == 201, resp.text
    p = resp.json()
    assert p["pattern_key"] == "第X条" and p["kind"] == "heading" and p["level"] == 3
    pid = p["id"]

    assert any(r["id"] == pid for r in client.get(PROFILES).json())

    resp = client.put(f"{PROFILES}/{pid}", json={"status": "candidate"})
    assert resp.status_code == 200 and resp.json()["status"] == "candidate"

    assert client.delete(f"{PROFILES}/{pid}").status_code == 204
    assert all(r["id"] != pid for r in client.get(PROFILES).json())


def test_numbering_profile_duplicate_and_bad_kind(client: TestClient) -> None:
    assert client.post(PROFILES, json={"pattern_key": "第X条", "kind": "heading"}).status_code == 201
    assert client.post(PROFILES, json={"pattern_key": "第X条", "kind": "heading"}).status_code == 409
    assert client.post(PROFILES, json={"pattern_key": "一、", "kind": "bogus"}).status_code == 409


def test_rule_injected_into_parse_end_to_end(client: TestClient, storage_tmp: Path) -> None:
    """端到端：自定义样式默认不识别 → 建规则 → /parse 注入后识别为章节。"""
    # 无规则：自定义样式名不在内置词典 → 不成章节
    assert "范围" not in _titles(_parse_custom(client))

    # 建规则（active）→ 再 /parse → 识别
    assert (
        client.post(RULES, json={"style_name": "公司专用标题样式", "level": 1}).status_code == 201
    )
    chapters = _parse_custom(client)
    assert "范围" in _titles(chapters)
    scope = next(c for c in chapters if c["title"] == "范围")
    assert scope["source_style_name"] == "公司专用标题样式"  # 归因字段已下穿


def test_source_style_name_persists_through_import(
    client: TestClient, storage_tmp: Path
) -> None:
    """M2：来源样式名经 import 落到 ProcedureNode，节点读 API 暴露（供编辑器「记住此样式」）。"""
    client.post(RULES, json={"style_name": "公司专用标题样式", "level": 1})
    data = (
        DocxBuilder()
        .heading("目的", level=1)
        .para("本程序的目的。")
        .styled_heading("范围", "公司专用标题样式")
        .para("适用于全公司。")
        .build()
    )
    token = client.post(UPLOADS, files={"file": ("a.docx", data, DOCX_MIME)}).json()[
        "upload_token"
    ]
    chapters = client.post(
        PARSE, json={"upload_token": token, "parse_mode": "smart"}
    ).json()["chapters"]
    leaf = client.post(FOLDER, json={"name": "导入夹", "prefix": "IM"}).json()["id"]
    imported = client.post(
        IMPORT, json={"name": "记录控制程序", "folder_id": leaf, "chapters": chapters}
    )
    assert imported.status_code == 201, imported.text
    proc_id = imported.json()["id"]

    nodes = client.get(f"/api/v1/procedures/{proc_id}/nodes").json()
    scope = next(n for n in nodes if n["heading_level"] is not None and "范围" in n["body"])
    assert scope["source_style_name"] == "公司专用标题样式"
