"""单元测试：import_service — content 节点落成内容块步骤 + 严格互斥归一化（Task A6）。"""

from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.models.chapter import ProcedureChapter
from app.models.step import ProcedureStep
from app.schemas.parse import ImportNodeIn
from app.services import import_service
from tests.conftest import Factory

META = RequestMeta(ip_address="127.0.0.1", user_agent="pytest", request_id="r1")


def _leaf(factory: Factory) -> str:
    leaf = factory.folder(name="叶子", prefix="QC", full_path="叶子")
    factory.sequence(leaf.id)
    return leaf.id


def test_content_node_imported_as_content_step(db: Session, factory: Factory, storage_tmp) -> None:
    proc = import_service.import_procedure(
        db, name="P", folder_id=_leaf(factory), description="",
        chapters=[ImportNodeIn(title="操作", content_type="chapter", children=[
            ImportNodeIn(content_type="content", rich_content="<p>正文</p>"),
        ])],
        meta=META,
    )
    steps = db.query(ProcedureStep).filter_by(procedure_id=proc.id, is_active=True).all()
    assert len(steps) == 1
    assert steps[0].kind == "content"
    assert steps[0].content == "<p>正文</p>"


def test_import_normalizes_intro_text_under_grouping_heading(db: Session, factory: Factory, storage_tmp) -> None:
    # 「引言」下：正文A + 子标题「子节」 —— 正文A 必须下沉为「子节」的前置内容块
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
    intro = db.query(ProcedureChapter).filter_by(procedure_id=proc.id, title="引言").one()
    sub = db.query(ProcedureChapter).filter_by(procedure_id=proc.id, title="子节").one()
    assert db.query(ProcedureStep).filter_by(chapter_id=intro.id, is_active=True).count() == 0
    contents = (
        db.query(ProcedureStep)
        .filter_by(chapter_id=sub.id, is_active=True)
        .order_by(ProcedureStep.sort_order)
        .all()
    )
    assert [c.content for c in contents] == ["<p>A</p>", "<p>B</p>"]
