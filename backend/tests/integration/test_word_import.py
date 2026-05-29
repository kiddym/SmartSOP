"""Word 导入端到端集成测试（M6.4）：upload → parse → import + assets。"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from tests.unit.parser._docx_builder import (
    empty_sop,
    styled_sop,
    tiny_png,
    unstyled_numbered_sop,
)

UPLOADS = "/api/v1/uploads"
PARSE = "/api/v1/parse"
IMPORT = "/api/v1/procedures/import"
FOLDER = "/api/v1/folders"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _leaf(client: TestClient, *, name: str = "导入夹", prefix: str = "IM") -> str:
    return client.post(FOLDER, json={"name": name, "prefix": prefix}).json()["id"]


def _upload(client: TestClient, data: bytes, name: str = "a.docx") -> str:
    resp = client.post(UPLOADS, files={"file": (name, data, DOCX_MIME)})
    assert resp.status_code == 200, resp.text
    return resp.json()["upload_token"]


def test_upload_rejects_non_docx(client: TestClient, storage_tmp: Path) -> None:
    resp = client.post(UPLOADS, files={"file": ("x.docx", b"not docx", DOCX_MIME)})
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "PARSE_FILE_INVALID"


def test_parse_methods(client: TestClient, storage_tmp: Path) -> None:
    resp = client.get(f"{PARSE}/methods")
    assert resp.status_code == 200
    keys = {m["key"] for m in resp.json()}
    assert keys == {"standard", "smart"}


def test_full_standard_flow(client: TestClient, storage_tmp: Path) -> None:
    leaf = _leaf(client)
    token = _upload(client, styled_sop())

    parsed = client.post(PARSE, json={"upload_token": token, "parse_mode": "standard"})
    assert parsed.status_code == 200, parsed.text
    body = parsed.json()
    assert body["metadata"]["body_start_detected_by"] == "first_styled_heading"
    assert body["review_required"] == 0
    assert len(body["assets"]) >= 1  # 内联图

    imported = client.post(
        IMPORT,
        json={"name": "记录控制程序", "folder_id": leaf, "chapters": body["chapters"]},
    )
    assert imported.status_code == 201, imported.text
    proc_id = imported.json()["id"]
    assert imported.json()["status"] == "DRAFT"

    nodes = client.get(f"/api/v1/procedures/{proc_id}/nodes").json()
    assert any("目的" in n["body"] for n in nodes if n["heading_level"] is not None)
    asset_urls = [
        m.group(0)
        for n in nodes
        for m in [re.search(r"/api/v1/procedures/[^/\"]+/assets/[0-9a-f-]{36}", n["body"])]
        if m
    ]
    assert asset_urls, "导入后应有永久 asset URL"
    served = client.get(asset_urls[0])
    assert served.status_code == 200
    assert served.content


def test_smart_unstyled_review_carried_into_draft(client: TestClient, storage_tmp: Path) -> None:
    leaf = _leaf(client)
    token = _upload(client, unstyled_numbered_sop())
    parsed = client.post(PARSE, json={"upload_token": token, "parse_mode": "smart"}).json()
    assert parsed["review_required"] >= 2

    # 带 review 直接导入：不再拦截，建成 DRAFT 草稿
    ok = client.post(
        IMPORT, json={"name": "带待确认", "folder_id": leaf, "chapters": parsed["chapters"]}
    )
    assert ok.status_code == 201, ok.text
    pid = ok.json()["id"]

    # review 状态带进草稿：至少一个节点 mark_status == 'review'
    nodes = client.get(f"/api/v1/procedures/{pid}/nodes").json()
    assert any(n["mark_status"] == "review" for n in nodes), "review 应带入草稿"


def test_standard_no_styled_heading_rejected(client: TestClient, storage_tmp: Path) -> None:
    token = _upload(client, unstyled_numbered_sop())
    resp = client.post(PARSE, json={"upload_token": token, "parse_mode": "standard"})
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "PARSE_TEMPLATE_INVALID"


def test_smart_empty_doc_no_headings(client: TestClient, storage_tmp: Path) -> None:
    token = _upload(client, empty_sop())
    resp = client.post(PARSE, json={"upload_token": token, "parse_mode": "smart"})
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "PARSE_NO_HEADINGS"


def test_invalid_token_rejected(client: TestClient, storage_tmp: Path) -> None:
    resp = client.post(PARSE, json={"upload_token": "ghost", "parse_mode": "smart"})
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "UPLOAD_TOKEN_INVALID"


def test_editor_asset_upload_and_serve(client: TestClient, storage_tmp: Path) -> None:
    leaf = _leaf(client)
    proc = client.post(
        "/api/v1/procedures",
        json={"folder_id": leaf, "name": "图片宿主", "level_of_use": "continuous"},
    ).json()
    pid = proc["id"]
    resp = client.post(
        f"/api/v1/procedures/{pid}/assets",
        files={"file": ("p.png", tiny_png(size=20), "image/png")},
    )
    assert resp.status_code == 201, resp.text
    asset = resp.json()
    assert asset["width"] == 20
    served = client.get(asset["url"])
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/png"


def test_editor_asset_rejects_too_large(client: TestClient, storage_tmp: Path) -> None:
    leaf = _leaf(client)
    pid = client.post(
        "/api/v1/procedures",
        json={"folder_id": leaf, "name": "h", "level_of_use": "continuous"},
    ).json()["id"]
    big = b"\x89PNG\r\n" + b"0" * (10 * 1024 * 1024 + 1)
    resp = client.post(
        f"/api/v1/procedures/{pid}/assets", files={"file": ("big.png", big, "image/png")}
    )
    assert resp.status_code == 413
    assert resp.json()["detail"]["code"] == "IMAGE_TOO_LARGE"


def test_import_content_with_children_dropped(client: TestClient, storage_tmp: Path) -> None:
    """content 节点为叶子：导入时其子内容块被静默丢弃，正常落库（§19 重构）。"""
    leaf = _leaf(client)
    tree = [
        {
            "title": "ch",
            "content_type": "chapter",
            "children": [
                {
                    "content_type": "content",
                    "rich_content": "<p>x</p>",
                    "children": [{"content_type": "content", "rich_content": "<p>y</p>"}],
                }
            ],
        }
    ]
    resp = client.post(IMPORT, json={"name": "内容子节点", "folder_id": leaf, "chapters": tree})
    assert resp.status_code == 201, resp.text
    pid = resp.json()["id"]
    nodes = client.get(f"/api/v1/procedures/{pid}/nodes").json()
    contents = [n for n in nodes if n["heading_level"] is None and n["kind"] == "node"]
    assert len(contents) == 1
    assert contents[0]["body"] == "<p>x</p>"


def test_temp_media_404_for_unknown_token(client: TestClient, storage_tmp: Path) -> None:
    resp = client.get("/api/v1/uploads/ghost/media/x.png")
    assert resp.status_code == 404


def test_import_stores_and_serves_source_docx(client: TestClient, storage_tmp: Path) -> None:
    leaf = _leaf(client)
    token = _upload(client, styled_sop(), name="源文件.docx")
    body = client.post(PARSE, json={"upload_token": token, "parse_mode": "standard"}).json()
    imported = client.post(
        IMPORT,
        json={"name": "带源文件", "folder_id": leaf, "upload_token": token, "chapters": body["chapters"]},
    )
    assert imported.status_code == 201, imported.text
    pid = imported.json()["id"]

    # 详情携带 has_source_docx=True，前端据此才拉预览（避免无源时的无谓 404）。
    assert client.get(f"/api/v1/procedures/{pid}").json()["has_source_docx"] is True

    served = client.get(f"/api/v1/procedures/{pid}/source-docx")
    assert served.status_code == 200
    assert served.headers["content-type"] == DOCX_MIME
    assert served.content
    # 流式下载头：inline + ASCII fallback + RFC5987（中文名经 quote 编码）。
    cd = served.headers["content-disposition"]
    assert cd.startswith("inline;")
    assert 'filename="' in cd
    assert "filename*=UTF-8''" in cd


def test_import_without_token_has_no_source_docx(client: TestClient, storage_tmp: Path) -> None:
    leaf = _leaf(client)
    token = _upload(client, styled_sop())
    body = client.post(PARSE, json={"upload_token": token, "parse_mode": "standard"}).json()
    imported = client.post(
        IMPORT, json={"name": "无源文件", "folder_id": leaf, "chapters": body["chapters"]}
    )
    pid = imported.json()["id"]
    assert client.get(f"/api/v1/procedures/{pid}").json()["has_source_docx"] is False
    assert client.get(f"/api/v1/procedures/{pid}/source-docx").status_code == 404


def test_delete_pure_draft_removes_source_docx(client: TestClient, storage_tmp: Path) -> None:
    leaf = _leaf(client)
    token = _upload(client, styled_sop())
    body = client.post(PARSE, json={"upload_token": token, "parse_mode": "standard"}).json()
    pid = client.post(
        IMPORT, json={"name": "可删草稿", "folder_id": leaf, "upload_token": token, "chapters": body["chapters"]}
    ).json()["id"]
    assert client.get(f"/api/v1/procedures/{pid}/source-docx").status_code == 200

    deleted = client.request("DELETE", f"/api/v1/procedures/{pid}", json={"reason": "弃用草稿"})
    assert deleted.status_code == 204, deleted.text
    assert client.get(f"/api/v1/procedures/{pid}/source-docx").status_code == 404


def test_delete_group_removes_source_docx(client: TestClient, storage_tmp: Path) -> None:
    """C1 回归：整组硬删（DELETE /procedure-groups/{id}）也清理源 docx，不留孤儿文件/行。"""
    from app import storage

    leaf = _leaf(client)
    token = _upload(client, styled_sop())
    body = client.post(PARSE, json={"upload_token": token, "parse_mode": "standard"}).json()
    imported = client.post(
        IMPORT,
        json={"name": "整组删草稿", "folder_id": leaf, "upload_token": token, "chapters": body["chapters"]},
    ).json()
    pid, gid = imported["id"], imported["procedure_group_id"]
    assert storage.source_docx_path(gid).exists()
    assert client.get(f"/api/v1/procedures/{pid}/source-docx").status_code == 200

    deleted = client.request("DELETE", f"/api/v1/procedure-groups/{gid}", json={"reason": "完全删除"})
    assert deleted.status_code == 204, deleted.text
    assert not storage.source_docx_path(gid).exists()  # 落盘文件已清，无孤儿
    assert client.get(f"/api/v1/procedures/{pid}/source-docx").status_code == 404


def test_delete_published_current_still_rejected(client: TestClient, storage_tmp: Path) -> None:
    leaf = _leaf(client)
    pid = client.post(
        "/api/v1/procedures", json={"folder_id": leaf, "name": "已发布", "level_of_use": "continuous"}
    ).json()["id"]
    rev = client.get(f"/api/v1/procedures/{pid}").json()["procedure"]["revision"]
    pub = client.post(
        f"/api/v1/procedures/{pid}/transition",
        json={"status": "PUBLISHED"},
        headers={"If-Match": str(rev)},
    )
    assert pub.status_code == 200, pub.text
    blocked = client.request("DELETE", f"/api/v1/procedures/{pid}", json={"reason": "x"})
    assert blocked.status_code == 400
    assert blocked.json()["detail"]["code"] == "PROCEDURE_IS_CURRENT"


def test_publish_blocked_while_review_pending(client: TestClient, storage_tmp: Path) -> None:
    leaf = _leaf(client)
    token = _upload(client, unstyled_numbered_sop())
    parsed = client.post(PARSE, json={"upload_token": token, "parse_mode": "smart"}).json()
    pid = client.post(
        IMPORT, json={"name": "待发布", "folder_id": leaf, "chapters": parsed["chapters"]}
    ).json()["id"]
    detail = client.get(f"/api/v1/procedures/{pid}").json()
    rev = detail["procedure"]["revision"]

    # 仍有 review → 发布被拦
    blocked = client.post(
        f"/api/v1/procedures/{pid}/transition",
        json={"status": "PUBLISHED"},
        headers={"If-Match": str(rev)},
    )
    assert blocked.status_code == 400
    assert blocked.json()["detail"]["code"] == "REVIEW_PENDING"

    # 清掉所有 review 后可发布（节点确认动作：batch 更新会把 review 清回 unmarked）
    nodes = client.get(f"/api/v1/procedures/{pid}/nodes").json()
    review_ids = [n["id"] for n in nodes if n["mark_status"] == "review"]
    assert review_ids  # 导入应产生待确认节点
    client.patch(
        f"/api/v1/procedures/{pid}/nodes:batch",
        json={"updates": {nid: {} for nid in review_ids}},
    )
    rev2 = client.get(f"/api/v1/procedures/{pid}").json()["procedure"]["revision"]
    ok = client.post(
        f"/api/v1/procedures/{pid}/transition",
        json={"status": "PUBLISHED"},
        headers={"If-Match": str(rev2)},
    )
    assert ok.status_code == 200, ok.text
