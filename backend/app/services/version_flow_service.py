"""版本管理流转（Phase 7 / api-specification §版本管理 / feature-clarifications §22 / §31）。

upgrade-version / rollback / deprecate / restore / copy / group 版本列表 / v1-DRAFT 整组硬删。
所有 fork（upgrade/rollback/restore/copy）= 新建 Procedure 记录 + 深拷贝章节/步骤树（附件元数据
复制属 Phase 9，本期不含）。同 group 仅 0/1 个 DRAFT（§22.9 应用层 check-then-act + DB draft_guard
兜底）；达 max_version_number 拒 PROCEDURE_VERSION_MAX（§31.1）。事务边界：只 flush，router 提交。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.errors import bad_request, conflict, not_found
from app.models.asset import ProcedureAssetReference
from app.models.attachment import ProcedureAttachment
from app.models.base import new_uuid, utcnow
from app.models.chapter import ProcedureChapter
from app.models.folder import Folder
from app.models.procedure import Procedure
from app.models.settings import ProcedureSettings
from app.models.step import ProcedureStep
from app.seed import ARCHIVED_FOLDER_NAME, DEPRECATED_FOLDER_NAME
from app.services import (
    attachment_service,
    audit_service,
    numbering_service,
    procedure_service,
    source_docx_service,
    version_service,
)
from app.services.sequence_generator import next_sequence_value

# 深拷贝时一并复制的章节 / 步骤字段（id / parent 关系单独重映射）。
_CHAPTER_COPY = ("title", "sort_order", "level", "skip_numbering")
_STEP_COPY = (
    "kind",
    "title",
    "content",
    "sort_order",
    "skip_numbering",
    "input_schema",
    "attachment_marks",
)


# --------------------------------------------------------------------------- #
# 内部工具
# --------------------------------------------------------------------------- #
def _get_settings(db: Session) -> ProcedureSettings:
    settings = db.execute(
        select(ProcedureSettings).where(ProcedureSettings.is_active.is_(True)).limit(1)
    ).scalar_one_or_none()
    if settings is None:
        raise not_found("NOT_FOUND", "全局设置缺失")
    return settings


def _group_max_version(db: Session, group_id: str) -> int:
    """同 group 内 active 记录的最大 version（评审 C1/C2：新版本须基于 group 最大值）。"""
    return int(
        db.execute(
            select(func.max(Procedure.version)).where(
                Procedure.procedure_group_id == group_id, Procedure.is_active.is_(True)
            )
        ).scalar_one()
        or 0
    )


def _next_version(db: Session, group_id: str, settings: ProcedureSettings) -> int:
    """fork 的新版本号 = group 最大版本 + 1；达上限拒绝（Q222/§31.1）。

    必须基于 group 最大值而非源记录版本：discard-draft 可能把非最高 ARCHIVED 提升为 current，
    若按 source.version+1 会与既有 active 版本撞 uq_tb_procedure_active_code_version（评审 C1/C2）。
    """
    group_max = _group_max_version(db, group_id)
    if group_max >= settings.max_version_number:
        raise bad_request("PROCEDURE_VERSION_MAX", "已达版本上限，请「复制为新程序」另起版本族")
    return group_max + 1


def _assert_no_active_draft(db: Session, group_id: str) -> None:
    """同 group 仅 0/1 个 DRAFT（§22.9 / §31.3）；DB draft_guard 为并发兜底。"""
    draft = db.execute(
        select(Procedure.id).where(
            Procedure.procedure_group_id == group_id,
            Procedure.is_active.is_(True),
            Procedure.status == "DRAFT",
        )
    ).first()
    if draft is not None:
        raise conflict("PROCEDURE_DRAFT_EXISTS", "该程序已存在草稿版本，请先发布或丢弃")


def _assert_not_deprecated(proc: Procedure) -> None:
    if proc.deprecated_at is not None:
        raise bad_request("PROCEDURE_DEPRECATED", "该程序已废止，请先恢复")


def _deprecated_folder(db: Session) -> Folder:
    folder = db.execute(
        select(Folder).where(
            Folder.name == DEPRECATED_FOLDER_NAME,
            Folder.system.is_(True),
            Folder.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if folder is None:
        raise not_found("NOT_FOUND", "「废止」系统文件夹缺失")
    return folder


def _archived_folder(db: Session) -> Folder:
    folder = db.execute(
        select(Folder).where(
            Folder.name == ARCHIVED_FOLDER_NAME,
            Folder.system.is_(True),
            Folder.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if folder is None:
        raise not_found("NOT_FOUND", "「归档」系统文件夹缺失")
    return folder


def _group_records(db: Session, group_id: str) -> list[Procedure]:
    return list(
        db.execute(
            select(Procedure).where(
                Procedure.procedure_group_id == group_id, Procedure.is_active.is_(True)
            )
        ).scalars()
    )


def _clone_tree(db: Session, src_id: str, dst_id: str) -> None:
    """深拷贝 src 程序的章节 / 步骤树到 dst（重映射 id / parent_id / chapter_id），并重算编号。"""
    chapters = list(
        db.execute(
            select(ProcedureChapter)
            .where(ProcedureChapter.procedure_id == src_id, ProcedureChapter.is_active.is_(True))
            .order_by(ProcedureChapter.level, ProcedureChapter.sort_order, ProcedureChapter.id)
        ).scalars()
    )
    id_map: dict[str, str] = {ch.id: new_uuid() for ch in chapters}
    for ch in chapters:
        clone = ProcedureChapter(
            id=id_map[ch.id],
            procedure_id=dst_id,
            parent_id=id_map.get(ch.parent_id) if ch.parent_id else None,
            mark_status="unmarked",  # 标记态为编辑期瞬态，复制版重置干净
            **{f: getattr(ch, f) for f in _CHAPTER_COPY},
        )
        db.add(clone)

    steps = list(
        db.execute(
            select(ProcedureStep).where(
                ProcedureStep.procedure_id == src_id, ProcedureStep.is_active.is_(True)
            )
        ).scalars()
    )
    for st in steps:
        clone_step = ProcedureStep(
            id=new_uuid(),
            procedure_id=dst_id,
            chapter_id=id_map.get(st.chapter_id) if st.chapter_id else None,
            **{f: getattr(st, f) for f in _STEP_COPY},
        )
        db.add(clone_step)

    db.flush()
    numbering_service.recompute(db, dst_id)


def _fork(
    db: Session,
    *,
    source: Procedure,
    content_source: Procedure,
    folder_id: str,
    version: int,
    version_update_notes: str = "",
) -> Procedure:
    """通用 fork：新建一条 DRAFT/is_current 记录，元字段取 source、内容树拷贝自 content_source。"""
    new_proc = Procedure(
        procedure_group_id=source.procedure_group_id,
        folder_id=folder_id,
        code=source.code,  # 同 group 共用 code，不重生成
        name=source.name,
        level_of_use=source.level_of_use,
        description=source.description,
        risk_level=source.risk_level,
        quality_level=source.quality_level,
        custom_values=dict(source.custom_values),
        signoff_enabled=source.signoff_enabled,
        version=version,
        is_current=True,
        status="DRAFT",
        revision=0,
        version_update_notes=version_update_notes,
    )
    db.add(new_proc)
    db.flush()
    _clone_tree(db, content_source.id, new_proc.id)
    # 附件元数据复制：取 content_source 版本（rollback 即 target，Q117/Q371）。
    attachment_service.copy_for_version(db, content_source.id, new_proc.id)
    return new_proc


def _audit(
    db: Session,
    proc: Procedure,
    action: str,
    meta: RequestMeta,
    *,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
    reason: str | None = None,
) -> None:
    audit_service.log_procedure_action(
        db,
        target_id=proc.id,
        procedure_group_id=proc.procedure_group_id,
        action=action,
        meta=meta,
        old_value=old_value,
        new_value=new_value,
        reason=reason or "",
    )


# --------------------------------------------------------------------------- #
# upgrade / rollback
# --------------------------------------------------------------------------- #
def upgrade_version(db: Session, proc_id: str, meta: RequestMeta) -> Procedure:
    proc = procedure_service.get_or_404(db, proc_id)
    _assert_not_deprecated(proc)
    if not (proc.is_current and proc.status == "PUBLISHED"):
        raise bad_request("PROCEDURE_STATUS_INVALID", "仅当前已发布版本可升级")
    settings = _get_settings(db)
    _assert_no_active_draft(db, proc.procedure_group_id)
    next_ver = _next_version(db, proc.procedure_group_id, settings)

    proc.is_current = False
    proc.status = "ARCHIVED"
    if proc.archived_at is None:
        proc.archived_at = utcnow()
    db.flush()

    new_proc = _fork(
        db, source=proc, content_source=proc, folder_id=proc.folder_id, version=next_ver
    )
    version_service.record_change(
        new_proc,
        "upgrade",
        previous_version=proc.version,
        description=f"基于 v{proc.version} 升级",
    )
    db.flush()
    _audit(
        db,
        new_proc,
        "upgrade",
        meta,
        old_value={"version": proc.version},
        new_value={"version": new_proc.version},
    )
    return new_proc


def rollback(
    db: Session, proc_id: str, target_version: int, reason: str, meta: RequestMeta
) -> Procedure:
    proc = procedure_service.get_or_404(db, proc_id)
    _assert_not_deprecated(proc)
    if not (proc.is_current and proc.status == "PUBLISHED"):
        raise bad_request("PROCEDURE_STATUS_INVALID", "仅当前已发布版本可回退")
    if not reason.strip():
        raise bad_request("ROLLBACK_REASON_REQUIRED", "请填写回退原因")

    target = db.execute(
        select(Procedure).where(
            Procedure.procedure_group_id == proc.procedure_group_id,
            Procedure.version == target_version,
            Procedure.is_active.is_(True),
            Procedure.status == "ARCHIVED",
            Procedure.is_current.is_(False),
        )
    ).scalar_one_or_none()
    if target is None:
        raise bad_request("ROLLBACK_TARGET_INVALID", "回退目标无效：须为同 group 的已归档历史版本")

    settings = _get_settings(db)
    _assert_no_active_draft(db, proc.procedure_group_id)
    next_ver = _next_version(db, proc.procedure_group_id, settings)

    proc.is_current = False
    proc.status = "ARCHIVED"
    if proc.archived_at is None:
        proc.archived_at = utcnow()
    db.flush()

    new_proc = _fork(
        db,
        source=target,  # 元字段 + 内容均取目标版本
        content_source=target,
        folder_id=proc.folder_id,
        version=next_ver,
        version_update_notes=f"回退自 v{target_version}：{reason}",
    )
    version_service.record_change(
        new_proc,
        "rollback",
        previous_version=proc.version,
        reason=reason,
        rollback_from_version=target_version,
        description=f"回退到 v{target_version}",
    )
    db.flush()
    _audit(
        db,
        new_proc,
        "rollback",
        meta,
        old_value={"version": proc.version},
        new_value={"version": new_proc.version, "target_version": target_version},
        reason=reason,
    )
    return new_proc


# --------------------------------------------------------------------------- #
# deprecate / restore（整 group）
# --------------------------------------------------------------------------- #
def deprecate(db: Session, proc_id: str, reason: str, meta: RequestMeta) -> Procedure:
    proc = procedure_service.get_or_404(db, proc_id)
    _assert_not_deprecated(proc)
    if not reason.strip():
        raise bad_request("REASON_REQUIRED", "请填写废弃原因")

    deprecated_folder = _deprecated_folder(db)
    now = utcnow()
    records = _group_records(db, proc.procedure_group_id)
    # deprecated_by 恒 NULL：本系统全匿名、无用户体系（Q322），无操作人可记录。
    for rec in records:
        rec.deprecated_from_folder_id = rec.folder_id
        rec.folder_id = deprecated_folder.id
        rec.deprecated_at = now
        if rec.status != "ARCHIVED":
            rec.status = "ARCHIVED"
            if rec.archived_at is None:
                rec.archived_at = now
    db.flush()
    _audit(db, proc, "deprecate", meta, new_value={"version_count": len(records)}, reason=reason)
    return proc


def archive_group(db: Session, proc_id: str, reason: str, meta: RequestMeta) -> Procedure:
    """归档整 group：与 deprecate 平行，语义差别在 folder（归档 vs 废止）。

    复用 deprecated_at / deprecated_from_folder_id 两个字段，让 restore 流程
    通用、不区分来源（spec §F §风险表）。字段重命名作为独立 topic。
    """
    proc = procedure_service.get_or_404(db, proc_id)
    proc_folder = db.get(Folder, proc.folder_id)
    if proc_folder is not None and proc_folder.system:
        raise bad_request("PROCEDURE_ARCHIVE_SYSTEM_FOLDER", "系统文件夹下的程序不可归档")
    if proc.status == "ARCHIVED":
        raise bad_request("PROCEDURE_ALREADY_ARCHIVED_OR_DEPRECATED", "该程序已归档或已废止")
    if not reason.strip():
        raise bad_request("REASON_REQUIRED", "请填写归档原因")

    archive_folder = _archived_folder(db)
    now = utcnow()
    records = _group_records(db, proc.procedure_group_id)
    # 与 deprecate 一致：deprecated_by 恒 NULL（Q322 全匿名）
    for rec in records:
        rec.deprecated_from_folder_id = rec.folder_id  # 复用字段记原 folder
        rec.folder_id = archive_folder.id
        rec.deprecated_at = now  # 复用 deprecated_at 让 restore 流程通用
        if rec.status != "ARCHIVED":
            rec.status = "ARCHIVED"
            if rec.archived_at is None:
                rec.archived_at = now
    db.flush()
    _audit(db, proc, "archive", meta, new_value={"version_count": len(records)}, reason=reason)
    return proc


def restore_preview(db: Session, proc_id: str) -> dict[str, Any]:
    proc = procedure_service.get_or_404(db, proc_id)
    origin_id = proc.deprecated_from_folder_id
    folder = db.get(Folder, origin_id) if origin_id else None
    folder_exists = folder is not None and folder.is_active
    return {
        "folder_exists": bool(folder_exists),
        "deprecated_from_folder_id": origin_id,
        "folder_full_path": folder.full_path if folder_exists and folder else None,
        "version_count": len(_group_records(db, proc.procedure_group_id)),
    }


def restore(
    db: Session, proc_id: str, reason: str, target_folder_id: str | None, meta: RequestMeta
) -> Procedure:
    proc = procedure_service.get_or_404(db, proc_id)
    if proc.deprecated_at is None:
        raise bad_request("PROCEDURE_NOT_DEPRECATED", "该程序未废止，无需恢复")
    if not reason.strip():
        raise bad_request("REASON_REQUIRED", "请填写恢复原因")

    origin_id = proc.deprecated_from_folder_id
    origin = db.get(Folder, origin_id) if origin_id else None
    if origin is not None and origin.is_active:
        target = origin
    else:
        if not target_folder_id:
            raise bad_request("RESTORE_FOLDER_MISSING", "原文件夹已删除，请指定目标文件夹")
        target = procedure_service.resolve_leaf_folder(db, target_folder_id)

    # 整 group 移出「废止」、清废止标记（Q180）。
    records = _group_records(db, proc.procedure_group_id)
    current = next((r for r in records if r.is_current), None)
    if current is None:
        raise not_found("NOT_FOUND", "版本族状态异常：无当前版本")
    for rec in records:
        rec.folder_id = target.id
        rec.deprecated_at = None
        rec.deprecated_by = None
        rec.deprecated_from_folder_id = None

    settings = _get_settings(db)
    _assert_no_active_draft(db, proc.procedure_group_id)
    next_ver = _next_version(db, proc.procedure_group_id, settings)
    current.is_current = False
    db.flush()

    new_proc = _fork(
        db,
        source=current,
        content_source=current,
        folder_id=target.id,
        version=next_ver,
    )
    version_service.record_change(
        new_proc,
        "restore",
        previous_version=current.version,
        reason=reason,
        description="从废止恢复",
    )
    db.flush()
    _audit(db, new_proc, "restore", meta, new_value={"version": new_proc.version}, reason=reason)
    return new_proc


# --------------------------------------------------------------------------- #
# copy（复制为新程序，新 group）
# --------------------------------------------------------------------------- #
def copy_procedure(
    db: Session, proc_id: str, target_folder_id: str, name: str | None, meta: RequestMeta
) -> Procedure:
    src = procedure_service.get_or_404(db, proc_id)  # 任意状态可作源（含 deprecated，Q179）
    folder = procedure_service.resolve_leaf_folder(db, target_folder_id)
    code = f"{folder.prefix}-{next_sequence_value(db, folder.id)}"

    new_proc = Procedure(
        procedure_group_id=new_uuid(),
        folder_id=folder.id,
        code=code,
        name=name.strip() if name and name.strip() else f"{src.name} (副本)",
        level_of_use=src.level_of_use,
        description=src.description,
        risk_level=src.risk_level,
        quality_level=src.quality_level,
        custom_values=dict(src.custom_values),
        version=1,
        is_current=True,
        status="DRAFT",
        revision=0,
    )
    db.add(new_proc)
    db.flush()
    _clone_tree(db, src.id, new_proc.id)
    # 复制所传 {id} 版本的附件元数据（Q238/Q371，不取 is_current）。
    attachment_service.copy_for_version(db, src.id, new_proc.id)
    version_service.record_create(new_proc, description=f"复制自 {src.code} v{src.version}")
    db.flush()
    _audit(db, new_proc, "copy", meta, new_value={"copy_from": src.id, "source_code": src.code})
    return new_proc


# --------------------------------------------------------------------------- #
# group 版本列表 / v1-DRAFT 整组硬删
# --------------------------------------------------------------------------- #
def list_group_versions(
    db: Session, group_id: str, count_only: bool
) -> tuple[list[Procedure], int]:
    count = int(
        db.execute(
            select(func.count())
            .select_from(Procedure)
            .where(Procedure.procedure_group_id == group_id, Procedure.is_active.is_(True))
        ).scalar_one()
    )
    if count_only:
        return [], count
    rows = list(
        db.execute(
            select(Procedure)
            .where(Procedure.procedure_group_id == group_id, Procedure.is_active.is_(True))
            .order_by(Procedure.created_at.desc(), Procedure.version.desc())
        ).scalars()
    )
    return rows, count


def delete_group(db: Session, group_id: str, reason: str, meta: RequestMeta) -> None:
    """硬删整 group——仅「单记录 + v1 + DRAFT + is_current」可删（Q177 / §22.13）。"""
    records = _group_records(db, group_id)
    if len(records) != 1:
        raise bad_request("PROCEDURE_GROUP_DELETE_FORBIDDEN", "仅含单一 v1 草稿的程序可整体删除")
    proc = records[0]
    if not (proc.version == 1 and proc.is_current and proc.status == "DRAFT"):
        raise bad_request("PROCEDURE_GROUP_DELETE_FORBIDDEN", "仅 v1 草稿当前版本可整体删除")

    # 审计先记（硬删后 proc 行消失；action 永久保留）。
    _audit(
        db,
        proc,
        "delete_group_v1_draft",
        meta,
        old_value={"code": proc.code, "name": proc.name},
        reason=reason,
    )

    # FK RESTRICT + 无 cascade → 手动按依赖顺序物理删除。
    db.execute(delete(ProcedureStep).where(ProcedureStep.procedure_id == proc.id))
    # 章节自引用：按真实树深拓扑删（叶先于父），不可依赖 level 列（仅 1-3 显示层级，
    # 同批删父子会触发自引用 FK RESTRICT 冲突，评审 H3）。
    rows = db.execute(
        select(ProcedureChapter.id, ProcedureChapter.parent_id).where(
            ProcedureChapter.procedure_id == proc.id
        )
    ).all()
    parent_of: dict[str, str | None] = {cid: pid for cid, pid in rows}
    remaining = set(parent_of)
    while remaining:
        referenced = {parent_of[c] for c in remaining if parent_of[c] in remaining}
        leaves = remaining - referenced
        if not leaves:  # 理论不会有环；兜底避免死循环
            leaves = remaining
        db.execute(delete(ProcedureChapter).where(ProcedureChapter.id.in_(leaves)))
        remaining -= leaves
    db.execute(
        delete(ProcedureAssetReference).where(ProcedureAssetReference.procedure_id == proc.id)
    )
    db.execute(delete(ProcedureAttachment).where(ProcedureAttachment.procedure_id == proc.id))
    # 原始 Word 源文件按 group 一份（行 + 落盘），随整组硬删一并清理（模型契约：随版本组删除即物理清理）。
    source_docx_service.delete_for_group(db, group_id)
    db.execute(delete(Procedure).where(Procedure.id == proc.id))
    db.flush()
