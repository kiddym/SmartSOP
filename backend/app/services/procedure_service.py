"""程序业务逻辑（api-specification §5.2 / data-model §3.3）。

Phase 3 = 基础 CRUD + 多版本骨架：
- 创建空白程序：code = folder.prefix + 序号；新 procedure_group_id；version=1；is_current；DRAFT。
- 列表 / 库 / 详情（嵌套树留待 Phase 4）。
- 更新：If-Match 乐观锁 + 仅 is_current=true 且 DRAFT 可改（PROCEDURE_READONLY）。
- 状态机：DRAFT→PUBLISHED→ARCHIVED，余皆 PROCEDURE_STATUS_INVALID。
- 删除：is_current 拒（PROCEDURE_IS_CURRENT）；非 current 软删（reason 必填）。
- 批量删 / 批量移动（原子，Q20/Q273）。

upgrade-version / rollback / deprecate / restore / copy / group 删除属 Phase 7。
事务边界：本模块只 flush，不 commit；由 router 提交。
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.errors import bad_request, not_found
from app.models.base import new_uuid, utcnow
from app.models.field import ProcedureField
from app.models.folder import Folder
from app.models.node import ProcedureNode
from app.models.procedure import Procedure
from app.schemas.attachment import AttachmentOut
from app.schemas.common import BatchDeleteFailure, BatchDeleteResult
from app.schemas.procedure import (
    BatchMoveIn,
    BatchMoveResult,
    DiscardDraftResult,
    FieldOut,
    ProcedureCreate,
    ProcedureDetail,
    ProcedureMeta,
    ProcedureOut,
    ProcedureUpdate,
    TransitionIn,
)
from app.services import (
    attachment_service,
    audit_service,
    field_service,
    optimistic_lock,
    version_service,
)
from app.services.sequence_generator import next_sequence_value

LEGAL_TRANSITIONS = {("DRAFT", "PUBLISHED"), ("PUBLISHED", "ARCHIVED")}

_SORTABLE: dict[str, Any] = {
    "created_at": Procedure.created_at,
    "updated_at": Procedure.updated_at,
    "code": Procedure.code,
    "name": Procedure.name,
}

_OUT_FIELDS = (
    "id",
    "procedure_group_id",
    "code",
    "name",
    "version",
    "is_current",
    "status",
    "folder_id",
    "level_of_use",
    "risk_level",
    "quality_level",
    "description",
    "signoff_enabled",
    "revision",
    "created_at",
    "updated_at",
)

_META_FIELDS = (
    "id",
    "procedure_group_id",
    "code",
    "name",
    "version",
    "is_current",
    "status",
    "folder_id",
    "description",
    "risk_level",
    "quality_level",
    "level_of_use",
    "custom_values",
    "version_update_notes",
    "signoff_enabled",
    "revision",
    "is_read",
    "read_at",
    "deprecated_from_folder_id",
    "deprecated_at",
    "archived_at",
    "version_change_log",
    "import_notes",
    "created_at",
    "updated_at",
)


# --------------------------------------------------------------------------- #
# 内部工具
# --------------------------------------------------------------------------- #
def _get(db: Session, proc_id: str) -> Procedure:
    proc = db.execute(
        select(Procedure).where(Procedure.id == proc_id, Procedure.is_active.is_(True))
    ).scalar_one_or_none()
    if proc is None:
        raise not_found("NOT_FOUND", "程序不存在")
    return proc


def _like_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _folder_full_path(db: Session, folder_id: str) -> str:
    folder = db.get(Folder, folder_id)
    return folder.full_path if folder is not None else ""


def _version_count(db: Session, group_id: str) -> int:
    return int(
        db.execute(
            select(func.count())
            .select_from(Procedure)
            .where(Procedure.procedure_group_id == group_id, Procedure.is_active.is_(True))
        ).scalar_one()
    )


def _out_model(db: Session, proc: Procedure) -> ProcedureOut:
    data: dict[str, Any] = {f: getattr(proc, f) for f in _OUT_FIELDS}
    data["folder_full_path"] = _folder_full_path(db, proc.folder_id)
    data["version_count_in_group"] = _version_count(db, proc.procedure_group_id)
    return ProcedureOut.model_validate(data)


def _meta_model(db: Session, proc: Procedure) -> ProcedureMeta:
    data: dict[str, Any] = {f: getattr(proc, f) for f in _META_FIELDS}
    data["folder_full_path"] = _folder_full_path(db, proc.folder_id)
    return ProcedureMeta.model_validate(data)


def to_meta(db: Session, proc: Procedure) -> ProcedureMeta:
    """供 router 在写操作后构造响应（含 derived folder_full_path）。"""
    return _meta_model(db, proc)


def get_or_404(db: Session, proc_id: str) -> Procedure:
    """公开取程序（不存在抛 NOT_FOUND）。供 version_flow_service 复用。"""
    return _get(db, proc_id)


def assert_node_host_editable(db: Session, procedure_id: str) -> None:
    """节点宿主可编辑守卫：查程序（不存在→404）+ 断言为当前版本草稿。供 node_service 复用，
    使"可编辑"判定的唯一权威集中于本模块。"""
    _assert_editable(get_or_404(db, procedure_id))


def resolve_leaf_folder(db: Session, folder_id: str) -> Folder:
    """公开校验叶子文件夹。供 version_flow_service 复用。"""
    return _resolve_leaf_folder(db, folder_id)


def _assert_editable(proc: Procedure) -> None:
    if not (proc.is_current and proc.status == "DRAFT"):
        raise bad_request("PROCEDURE_READONLY", "仅当前版本的草稿可编辑")


def _assert_not_deprecated(proc: Procedure) -> None:
    """deprecated group 守卫（§13.4 / §22）：废止后修改类接口一律拒绝。"""
    if proc.deprecated_at is not None:
        raise bad_request("PROCEDURE_DEPRECATED", "该程序已废止，请先恢复")


def _resolve_leaf_folder(db: Session, folder_id: str) -> Folder:
    """校验目标为可存程序的叶子文件夹（system=false、无子、有 prefix）。"""
    folder = db.execute(
        select(Folder).where(Folder.id == folder_id, Folder.is_active.is_(True))
    ).scalar_one_or_none()
    if folder is None:
        raise not_found("NOT_FOUND", "目标文件夹不存在")
    if folder.system:
        raise bad_request("PROCEDURE_FOLDER_REQUIRED", "不能在系统文件夹下存放程序")
    has_children = (
        db.execute(
            select(Folder.id).where(Folder.parent_id == folder.id, Folder.is_active.is_(True))
        ).first()
        is not None
    )
    if has_children:
        raise bad_request("PROCEDURE_FOLDER_REQUIRED", "只能在叶子文件夹下存放程序")
    if not folder.prefix:
        raise bad_request("PROCEDURE_FOLDER_REQUIRED", "该文件夹未配置编号前缀")
    return folder


# --------------------------------------------------------------------------- #
# 写操作
# --------------------------------------------------------------------------- #
def create_procedure(db: Session, data: ProcedureCreate, meta: RequestMeta) -> Procedure:
    folder = _resolve_leaf_folder(db, data.folder_id)
    field_service.validate_values(db, data.custom_values, require_check=False)
    code = f"{folder.prefix}-{next_sequence_value(db, folder.id)}"

    proc = Procedure(
        procedure_group_id=new_uuid(),
        folder_id=folder.id,
        code=code,
        name=data.name,
        level_of_use=data.level_of_use,
        description=data.description,
        risk_level=data.risk_level,
        quality_level=data.quality_level,
        custom_values=data.custom_values,
        version=1,
        is_current=True,
        status="DRAFT",
        revision=0,
    )
    db.add(proc)
    db.flush()
    version_service.record_create(proc, description="创建程序")
    audit_service.log_procedure_action(
        db,
        target_id=proc.id,
        procedure_group_id=proc.procedure_group_id,
        action="create",
        meta=meta,
        new_value={"code": code, "name": proc.name, "folder_id": folder.id},
    )
    return proc


def update_procedure(
    db: Session, proc_id: str, data: ProcedureUpdate, expected_revision: int, meta: RequestMeta
) -> Procedure:
    proc = _get(db, proc_id)
    _assert_not_deprecated(proc)
    _assert_editable(proc)
    optimistic_lock.verify_revision(proc.revision, expected_revision)
    field_service.validate_values(db, data.custom_values, require_check=False)

    before = {
        "name": proc.name,
        "description": proc.description,
        "risk_level": proc.risk_level,
        "quality_level": proc.quality_level,
        "level_of_use": proc.level_of_use,
        "version_update_notes": proc.version_update_notes,
        "signoff_enabled": proc.signoff_enabled,
    }
    proc.name = data.name
    proc.description = data.description
    proc.risk_level = data.risk_level
    proc.quality_level = data.quality_level
    proc.level_of_use = data.level_of_use
    proc.custom_values = data.custom_values
    proc.version_update_notes = data.version_update_notes
    proc.signoff_enabled = data.signoff_enabled
    optimistic_lock.bump(proc)
    db.flush()

    after = {
        "name": proc.name,
        "description": proc.description,
        "risk_level": proc.risk_level,
        "quality_level": proc.quality_level,
        "level_of_use": proc.level_of_use,
        "version_update_notes": proc.version_update_notes,
        "signoff_enabled": proc.signoff_enabled,
    }
    old_value, new_value = audit_service.compute_diff(before, after)
    audit_service.log_procedure_action(
        db,
        target_id=proc.id,
        procedure_group_id=proc.procedure_group_id,
        action="update",
        meta=meta,
        old_value=old_value,
        new_value=new_value,
    )
    return proc


def transition(
    db: Session, proc_id: str, data: TransitionIn, expected_revision: int, meta: RequestMeta
) -> Procedure:
    proc = _get(db, proc_id)
    _assert_not_deprecated(proc)
    if not proc.is_current:
        raise bad_request("PROCEDURE_READONLY", "仅当前版本可切换状态")
    optimistic_lock.verify_revision(proc.revision, expected_revision)

    old_status = proc.status
    target = data.status
    if (old_status, target) not in LEGAL_TRANSITIONS:
        raise bad_request("PROCEDURE_STATUS_INVALID", f"非法状态切换：{old_status} → {target}")
    # v2+ 发布必须有更新说明（Q178）
    if target == "PUBLISHED" and proc.version > 1 and not proc.version_update_notes.strip():
        raise bad_request("VERSION_UPDATE_NOTES_REQUIRED", "请先填写本次版本的更新说明")
    # 发布前强制必填自定义字段（Q367/Q368）
    if target == "PUBLISHED":
        field_service.validate_values(db, proc.custom_values, require_check=True)
        pending = db.execute(
            select(func.count())
            .select_from(ProcedureNode)
            .where(
                ProcedureNode.procedure_id == proc.id,
                ProcedureNode.is_active.is_(True),
                ProcedureNode.mark_status == "review",
            )
        ).scalar_one()
        if pending:
            raise bad_request("REVIEW_PENDING", f"仍有 {pending} 个待确认节点，请先全部处理")

    proc.status = target
    if target == "ARCHIVED":
        proc.archived_at = utcnow()
    if target == "PUBLISHED":
        version_service.record_change(proc, "publish", description="发布")
    optimistic_lock.bump(proc)
    db.flush()

    audit_service.log_procedure_action(
        db,
        target_id=proc.id,
        procedure_group_id=proc.procedure_group_id,
        action="publish" if target == "PUBLISHED" else "transition",
        meta=meta,
        old_value={"status": old_status},
        new_value={"status": target},
        reason=data.reason,
    )
    return proc


def delete_procedure(
    db: Session, proc_id: str, reason: str, meta: RequestMeta
) -> DiscardDraftResult | None:
    """软删单版本；is_current=true AND DRAFT AND version>1 走「丢弃 DRAFT」特殊路径（§22.11）。

    返回 DiscardDraftResult 表示走了丢弃路径（router 返 200 + body）；返回 None 表示普通软删（204）。
    """
    proc = _get(db, proc_id)
    if proc.is_current:
        # 丢弃 DRAFT：v>1 草稿当前版本 → 软删 + 把同 group 最高版本的 ARCHIVED 提升为 current（§22.11）
        if proc.status == "DRAFT" and proc.version > 1:
            return _discard_draft(db, proc, reason, meta)
        if proc.status == "DRAFT" and proc.version == 1:
            # 纯草稿（唯一版本、从未发布）：整组丢弃，连带清源 docx（P1 / cleanup=C 手动删）
            from app.services import source_docx_service  # 局部导入避免循环

            source_docx_service.delete_for_group(db, proc.procedure_group_id)
            proc.is_current = False
            _soft_delete(db, proc)
            audit_service.log_procedure_action(
                db,
                target_id=proc.id,
                procedure_group_id=proc.procedure_group_id,
                action="delete",
                meta=meta,
                old_value={"code": proc.code, "name": proc.name},
                reason=reason,
            )
            return None
        raise bad_request("PROCEDURE_IS_CURRENT", "当前版本不可直接删除")
    _soft_delete(db, proc)
    audit_service.log_procedure_action(
        db,
        target_id=proc.id,
        procedure_group_id=proc.procedure_group_id,
        action="delete",
        meta=meta,
        old_value={"code": proc.code, "name": proc.name},
        reason=reason,
    )
    return None


def _discard_draft(
    db: Session, proc: Procedure, reason: str, meta: RequestMeta
) -> DiscardDraftResult:
    proc.is_current = False
    _soft_delete(db, proc)  # flush 内含
    # 同 group 内最高版本的 active ARCHIVED 提升为 current（状态保持 ARCHIVED，Q175）
    new_current = db.execute(
        select(Procedure)
        .where(
            Procedure.procedure_group_id == proc.procedure_group_id,
            Procedure.is_active.is_(True),
            Procedure.status == "ARCHIVED",
        )
        .order_by(Procedure.version.desc())
        .limit(1)
    ).scalar_one_or_none()
    if new_current is None:
        raise bad_request("PROCEDURE_IS_CURRENT", "无可回退的历史版本")
    new_current.is_current = True
    db.flush()
    audit_service.log_procedure_action(
        db,
        target_id=proc.id,
        procedure_group_id=proc.procedure_group_id,
        action="discard-draft",
        meta=meta,
        old_value={"version": proc.version},
        new_value={"new_current_version": new_current.version},
        reason=reason,
    )
    return DiscardDraftResult(
        deleted_id=proc.id,
        new_current_id=new_current.id,
        new_current_version=new_current.version,
    )


def _soft_delete(db: Session, proc: Procedure) -> None:
    proc.is_active = False
    proc.deleted_at = utcnow()
    db.flush()


def batch_delete(db: Session, ids: list[str], reason: str, meta: RequestMeta) -> BatchDeleteResult:
    """原子批量软删（Q20）：先全量校验，任一失败则全部不动。"""
    seen: set[str] = set()
    unique_ids: list[str] = []
    for pid in ids:
        if pid not in seen:
            seen.add(pid)
            unique_ids.append(pid)

    failed: list[BatchDeleteFailure] = []
    targets: list[Procedure] = []
    for pid in unique_ids:
        try:
            proc = _get(db, pid)
            if proc.is_current:
                raise bad_request("PROCEDURE_IS_CURRENT", "当前版本不可直接删除")
        except HTTPException as exc:
            detail: dict[str, Any] = exc.detail if isinstance(exc.detail, dict) else {}
            failed.append(
                BatchDeleteFailure(
                    id=pid,
                    code=str(detail.get("code", "")),
                    message=str(detail.get("message", "")),
                )
            )
            continue
        targets.append(proc)

    if failed:
        return BatchDeleteResult(deleted_ids=[], failed=failed)

    deleted_ids: list[str] = []
    for proc in targets:
        _soft_delete(db, proc)
        audit_service.log_procedure_action(
            db,
            target_id=proc.id,
            procedure_group_id=proc.procedure_group_id,
            action="delete",
            meta=meta,
            old_value={"code": proc.code, "name": proc.name},
            reason=reason,
        )
        deleted_ids.append(proc.id)
    return BatchDeleteResult(deleted_ids=deleted_ids, failed=[])


def batch_move(db: Session, data: BatchMoveIn, meta: RequestMeta) -> BatchMoveResult:
    """原子批量移动到叶子文件夹（code 不变，Q22/Q273）。目标非法则整请求失败。"""
    target = _resolve_leaf_folder(db, data.target_folder_id)

    seen: set[str] = set()
    unique_ids: list[str] = []
    for pid in data.ids:
        if pid not in seen:
            seen.add(pid)
            unique_ids.append(pid)

    failed: list[BatchDeleteFailure] = []
    targets: list[Procedure] = []
    for pid in unique_ids:
        try:
            targets.append(_get(db, pid))
        except HTTPException as exc:
            detail: dict[str, Any] = exc.detail if isinstance(exc.detail, dict) else {}
            failed.append(
                BatchDeleteFailure(
                    id=pid,
                    code=str(detail.get("code", "")),
                    message=str(detail.get("message", "")),
                )
            )
            continue

    if failed:
        return BatchMoveResult(moved_ids=[], failed=failed)

    moved_ids: list[str] = []
    for proc in targets:
        old_folder_id = proc.folder_id
        proc.folder_id = target.id
        audit_service.log_procedure_action(
            db,
            target_id=proc.id,
            procedure_group_id=proc.procedure_group_id,
            action="move",
            meta=meta,
            old_value={"folder_id": old_folder_id},
            new_value={"folder_id": target.id},
        )
        moved_ids.append(proc.id)
    db.flush()
    return BatchMoveResult(moved_ids=moved_ids, failed=[])


# --------------------------------------------------------------------------- #
# 读操作
# --------------------------------------------------------------------------- #
def _apply_sort(stmt: Any, sort: str) -> Any:
    desc = sort.startswith("-")
    field = _SORTABLE.get(sort.lstrip("-"), Procedure.updated_at)
    return stmt.order_by(field.desc() if desc else field.asc())


def _paginate(db: Session, stmt: Any, page: int, page_size: int) -> tuple[list[Procedure], int]:
    total = db.execute(
        select(func.count()).select_from(stmt.order_by(None).subquery())
    ).scalar_one()
    rows = list(db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars())
    return rows, int(total)


def list_procedures(
    db: Session,
    *,
    page: int,
    page_size: int,
    sort: str,
    search: str | None,
    folder_id: str | None,
    status: str | None,
) -> tuple[list[ProcedureOut], int]:
    """程序库列表：每 group 一行（is_current）。search 跨全库、覆盖 code+name+description。"""
    stmt = select(Procedure).where(Procedure.is_active.is_(True), Procedure.is_current.is_(True))
    if search:
        # Q278/Q281：search 时忽略 folder_id，跨全库，多词 AND
        for token in search.split():
            like = f"%{_like_escape(token)}%"
            stmt = stmt.where(
                or_(
                    Procedure.code.ilike(like, escape="\\"),
                    Procedure.name.ilike(like, escape="\\"),
                    Procedure.description.ilike(like, escape="\\"),
                )
            )
    elif folder_id:
        # Q278/Q281：仅 search 时忽略 folder_id 跨全库；status 过滤始终生效
        stmt = stmt.where(Procedure.folder_id == folder_id)
    if status:
        stmt = stmt.where(Procedure.status == status)

    rows, total = _paginate(db, _apply_sort(stmt, sort), page, page_size)
    return [_out_model(db, p) for p in rows], total


def list_library(
    db: Session, *, page: int, page_size: int, sort: str, search: str | None, folder_id: str | None
) -> tuple[list[ProcedureOut], int]:
    """已发布程序库：status=PUBLISHED 且 is_current=true。"""
    stmt = select(Procedure).where(
        Procedure.is_active.is_(True),
        Procedure.is_current.is_(True),
        Procedure.status == "PUBLISHED",
    )
    if search:
        for token in search.split():
            like = f"%{_like_escape(token)}%"
            stmt = stmt.where(
                or_(
                    Procedure.code.ilike(like, escape="\\"),
                    Procedure.name.ilike(like, escape="\\"),
                    Procedure.description.ilike(like, escape="\\"),
                )
            )
    elif folder_id:
        stmt = stmt.where(Procedure.folder_id == folder_id)

    rows, total = _paginate(db, _apply_sort(stmt, sort), page, page_size)
    return [_out_model(db, p) for p in rows], total


def get_detail(db: Session, proc_id: str) -> ProcedureDetail:
    proc = _get(db, proc_id)
    fields = list(
        db.execute(
            select(ProcedureField)
            .where(ProcedureField.is_active.is_(True), ProcedureField.status == "active")
            .order_by(ProcedureField.sort_order)
        ).scalars()
    )
    from app.services import source_docx_service  # 局部导入避免循环

    return ProcedureDetail(
        procedure=_meta_model(db, proc),
        attachments=[
            AttachmentOut.model_validate(a) for a in attachment_service.rows_for(db, proc_id)
        ],
        fields=[FieldOut.model_validate(f) for f in fields],
        has_source_docx=source_docx_service.exists_for_procedure(db, proc_id),
    )
