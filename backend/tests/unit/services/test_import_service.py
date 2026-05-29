"""单元测试：import_service 直接落 ProcedureNode（B4a）。"""

from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.models.chapter import ProcedureChapter
from app.models.node import ProcedureNode
from app.models.step import ProcedureStep
from app.schemas.parse import ImportNodeIn
from app.services import import_service
from tests.conftest import Factory

META = RequestMeta(ip_address="127.0.0.1", user_agent="pytest", request_id="r1")


def _leaf(factory: Factory) -> str:
    leaf = factory.folder(name="叶子", prefix="QC", full_path="叶子")
    factory.sequence(leaf.id)
    return leaf.id


def test_import_builds_nodes_in_document_order(db: Session, factory: Factory, storage_tmp) -> None:
    # 「引言」下：正文A 然后 子标题「子节」（子节下含正文B）——不再下沉/归一化，保留文档序
    proc = import_service.import_procedure(
        db, name="P", folder_id=_leaf(factory), description="",
        chapters=[ImportNodeIn(title="引言", content_type="chapter", children=[
            ImportNodeIn(content_type="content", rich_content="<p>A</p>"),
            ImportNodeIn(title="子节", content_type="chapter", children=[
                ImportNodeIn(content_type="content", rich_content="<p>B</p>"),
            ]),
        ])],
        meta=META,
    )
    nodes = (
        db.query(ProcedureNode)
        .filter_by(procedure_id=proc.id, is_active=True)
        .order_by(ProcedureNode.sort_order)
        .all()
    )
    assert [(n.heading_level, n.kind, n.body) for n in nodes] == [
        (1, "node", "<p>引言</p>"),
        (None, "node", "<p>A</p>"),
        (2, "node", "<p>子节</p>"),
        (None, "node", "<p>B</p>"),
    ]
    # 不再建旧表行
    assert db.query(ProcedureChapter).filter_by(procedure_id=proc.id).count() == 0
    assert db.query(ProcedureStep).filter_by(procedure_id=proc.id).count() == 0


def test_import_carries_review_mark_on_heading(db: Session, factory: Factory, storage_tmp) -> None:
    proc = import_service.import_procedure(
        db, name="P", folder_id=_leaf(factory), description="",
        chapters=[ImportNodeIn(title="待审", content_type="chapter", mark_status="review")],
        meta=META,
    )
    n = db.query(ProcedureNode).filter_by(procedure_id=proc.id, is_active=True).one()
    assert n.mark_status == "review"
    assert n.heading_level == 1
    assert n.body == "<p>待审</p>"
