"""文件夹业务逻辑（data-model §3.1 / api-specification §5.1 / Q246–Q252）。

不变式与约束：
- 最大嵌套深度 5（根=第 1 层），应用层校验（`FOLDER_DEPTH_EXCEEDED`）。
- 移动（改 parent_id）禁止形成循环（`FOLDER_CYCLE_DETECTED`）。
- 同 parent 下名称唯一（活跃行，`FOLDER_NAME_DUPLICATE`）。
- 叶子 prefix 全局唯一且**永久占用**：校验既有文件夹 prefix + 历史 code 前缀（Q249，
  `FOLDER_PREFIX_DUPLICATE`）。
- 容器 xor 叶子：含程序的文件夹禁止新增 / 移入子文件夹（Q247，`FOLDER_HAS_PROCEDURES`）。
- 删除硬约束：含子文件夹或程序即拒（`FOLDER_NOT_EMPTY`）；系统文件夹禁删改
  （`FOLDER_SYSTEM_PROTECTED`）。
- 文件夹**不走乐观锁**（Q18 仅 tb_procedure.revision）。

事务边界：本模块只 flush，不 commit；由 router 提交（seed 等启动脚本例外）。
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import RequestMeta
from app.errors import bad_request, conflict, not_found
from app.models.base import utcnow
from app.models.folder import Folder, FolderSequence
from app.models.procedure import Procedure
from app.schemas.folder import (
    BatchDeleteFailure,
    BatchDeleteResult,
    FolderCreate,
    FolderUpdate,
)
from app.services import audit_service

MAX_DEPTH = 5
PATH_SEP = " / "


# --------------------------------------------------------------------------- #
# 内部查询 / 工具
# --------------------------------------------------------------------------- #
def _get(db: Session, folder_id: str) -> Folder:
    """取活跃文件夹，不存在抛 404。"""
    folder = db.execute(
        select(Folder).where(Folder.id == folder_id, Folder.is_active.is_(True))
    ).scalar_one_or_none()
    if folder is None:
        raise not_found("NOT_FOUND", "文件夹不存在")
    return folder


def _active_children(db: Session, folder_id: str) -> list[Folder]:
    return list(
        db.execute(
            select(Folder).where(Folder.parent_id == folder_id, Folder.is_active.is_(True))
        ).scalars()
    )


def _has_active_procedures(db: Session, folder_id: str) -> bool:
    return (
        db.execute(
            select(Procedure.id).where(
                Procedure.folder_id == folder_id, Procedure.is_active.is_(True)
            )
        ).first()
        is not None
    )


def _depth_of(db: Session, folder: Folder) -> int:
    """文件夹深度（根=1）。沿 parent 链上溯，带防腐环保护。"""
    depth = 1
    seen: set[str] = {folder.id}
    pid = folder.parent_id
    while pid is not None and pid not in seen:
        depth += 1
        seen.add(pid)
        parent = db.get(Folder, pid)
        if parent is None:
            break
        pid = parent.parent_id
    return depth


def _subtree_height(db: Session, folder_id: str) -> int:
    """子树高度（叶子=0）：folder 下最深活跃后代相对 folder 的层数。"""
    height = 0
    frontier = [folder_id]
    while frontier:
        rows = list(
            db.execute(
                select(Folder.id).where(Folder.parent_id.in_(frontier), Folder.is_active.is_(True))
            ).scalars()
        )
        if not rows:
            break
        height += 1
        frontier = rows
    return height


def _descendant_ids(db: Session, folder_id: str) -> set[str]:
    """所有活跃后代 id（不含自身），用于循环检测。"""
    result: set[str] = set()
    frontier = [folder_id]
    while frontier:
        rows = list(
            db.execute(
                select(Folder.id).where(Folder.parent_id.in_(frontier), Folder.is_active.is_(True))
            ).scalars()
        )
        fresh = [r for r in rows if r not in result]
        result.update(fresh)
        frontier = fresh
    return result


def _name_taken(
    db: Session, parent_id: str | None, name: str, exclude_id: str | None = None
) -> bool:
    stmt = select(Folder.id).where(Folder.name == name, Folder.is_active.is_(True))
    stmt = stmt.where(
        Folder.parent_id.is_(None) if parent_id is None else Folder.parent_id == parent_id
    )
    if exclude_id is not None:
        stmt = stmt.where(Folder.id != exclude_id)
    return db.execute(stmt).first() is not None


def _like_escape(value: str) -> str:
    """转义 LIKE 通配符，避免 prefix 中的 % / _ 误匹配。"""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _prefix_in_use(db: Session, prefix: str, exclude_id: str | None = None) -> bool:
    """prefix 是否已被占用：其它活跃文件夹 OR 任何历史 code（Q249 永久占用）。"""
    folder_stmt = select(Folder.id).where(Folder.prefix == prefix, Folder.is_active.is_(True))
    if exclude_id is not None:
        folder_stmt = folder_stmt.where(Folder.id != exclude_id)
    if db.execute(folder_stmt).first() is not None:
        return True
    # 历史 code 前缀：含软删行（永久占用），按 `{prefix}-%` 匹配（连字符锚定，避免 QC 命中 QCD）
    pattern = f"{_like_escape(prefix)}-%"
    code_stmt = select(Procedure.id).where(Procedure.code.like(pattern, escape="\\"))
    return db.execute(code_stmt).first() is not None


def _full_path(parent: Folder | None, name: str) -> str:
    if parent is None:
        return name
    return f"{parent.full_path}{PATH_SEP}{name}"


def _recompute_descendant_paths(db: Session, folder: Folder) -> None:
    """folder.full_path 已更新后，逐层重算所有活跃后代的 full_path。"""
    frontier = [folder]
    while frontier:
        nxt: list[Folder] = []
        for parent in frontier:
            for child in _active_children(db, parent.id):
                child.full_path = f"{parent.full_path}{PATH_SEP}{child.name}"
                nxt.append(child)
        frontier = nxt
    db.flush()


def _snapshot(folder: Folder) -> dict[str, Any]:
    return {
        "name": folder.name,
        "prefix": folder.prefix,
        "parent_id": folder.parent_id,
        "full_path": folder.full_path,
    }


def _get_active_sequence(db: Session, folder_id: str) -> FolderSequence | None:
    return db.execute(
        select(FolderSequence).where(
            FolderSequence.folder_id == folder_id, FolderSequence.is_active.is_(True)
        )
    ).scalar_one_or_none()


def _get_sequence_any(db: Session, folder_id: str) -> FolderSequence | None:
    """取序列行（含软删）。folder_id 唯一，故最多一行——复用避免 unique 冲突。"""
    return db.execute(
        select(FolderSequence).where(FolderSequence.folder_id == folder_id)
    ).scalar_one_or_none()


# --------------------------------------------------------------------------- #
# 写操作
# --------------------------------------------------------------------------- #
def create_folder(db: Session, data: FolderCreate, meta: RequestMeta) -> Folder:
    parent: Folder | None = None
    if data.parent_id is not None:
        parent = _get(db, data.parent_id)
        if _has_active_procedures(db, parent.id):
            raise bad_request(
                "FOLDER_HAS_PROCEDURES",
                "该文件夹已存放程序，不能再新建子文件夹（请先移走程序）",
            )
        if _depth_of(db, parent) + 1 > MAX_DEPTH:
            raise bad_request("FOLDER_DEPTH_EXCEEDED", f"文件夹最多 {MAX_DEPTH} 级嵌套")

    if _name_taken(db, data.parent_id, data.name):
        raise conflict("FOLDER_NAME_DUPLICATE", "同一父目录下已存在该名称的文件夹", field="name")

    prefix = data.prefix.strip()
    if prefix and _prefix_in_use(db, prefix):
        raise conflict(
            "FOLDER_PREFIX_DUPLICATE", "前缀已被占用，含历史程序使用过的前缀", field="prefix"
        )

    folder = Folder(
        name=data.name,
        prefix=prefix,
        parent_id=data.parent_id,
        system=False,
        full_path=_full_path(parent, data.name),
    )
    db.add(folder)
    db.flush()

    # 叶子（prefix 非空）建编号序列；中间容器不建（Q247）
    if prefix:
        db.add(
            FolderSequence(
                folder_id=folder.id,
                current_value=0,
                sequence_digits=data.sequence_digits,
            )
        )
        db.flush()

    audit_service.log_folder_action(
        db, target_id=folder.id, action="create", meta=meta, new_value=_snapshot(folder)
    )
    return folder


def update_folder(db: Session, folder_id: str, data: FolderUpdate, meta: RequestMeta) -> Folder:
    folder = _get(db, folder_id)
    if folder.system:
        raise bad_request("FOLDER_SYSTEM_PROTECTED", "系统文件夹不可删除或修改")

    before = _snapshot(folder)
    new_parent_id = data.parent_id
    moving = new_parent_id != folder.parent_id

    new_parent: Folder | None = None
    if new_parent_id is not None:
        new_parent = _get(db, new_parent_id)

    if moving:
        if new_parent_id == folder.id or (
            new_parent_id is not None and new_parent_id in _descendant_ids(db, folder.id)
        ):
            raise bad_request("FOLDER_CYCLE_DETECTED", "移动会形成循环结构，已阻止")
        if new_parent is not None and _has_active_procedures(db, new_parent.id):
            raise bad_request(
                "FOLDER_HAS_PROCEDURES",
                "目标文件夹已存放程序，不能移入子文件夹（请先移走程序）",
            )
        base_depth = (_depth_of(db, new_parent) + 1) if new_parent is not None else 1
        if base_depth + _subtree_height(db, folder.id) > MAX_DEPTH:
            raise bad_request("FOLDER_DEPTH_EXCEEDED", f"文件夹最多 {MAX_DEPTH} 级嵌套")

    if _name_taken(db, new_parent_id, data.name, exclude_id=folder.id):
        raise conflict("FOLDER_NAME_DUPLICATE", "同一父目录下已存在该名称的文件夹", field="name")

    new_prefix = data.prefix.strip()
    if (
        new_prefix != folder.prefix
        and new_prefix
        and _prefix_in_use(db, new_prefix, exclude_id=folder.id)
    ):
        raise conflict(
            "FOLDER_PREFIX_DUPLICATE", "前缀已被占用，含历史程序使用过的前缀", field="prefix"
        )

    name_changed = data.name != before["name"]
    folder.name = data.name
    folder.parent_id = new_parent_id
    folder.prefix = new_prefix
    folder.full_path = _full_path(new_parent, data.name)
    db.flush()
    # full_path 仅在改名 / 移动时变化，否则跳过整子树重算
    if moving or name_changed:
        _recompute_descendant_paths(db, folder)

    _maintain_sequence(db, folder, new_prefix, data.sequence_digits)

    action = "move" if moving else "update"
    old_value, new_value = audit_service.compute_diff(before, _snapshot(folder))
    audit_service.log_folder_action(
        db,
        target_id=folder.id,
        action=action,
        meta=meta,
        old_value=old_value,
        new_value=new_value,
    )
    return folder


def _maintain_sequence(
    db: Session, folder: Folder, new_prefix: str, sequence_digits: int | None
) -> None:
    """同步编号序列与叶子/容器状态（Q247）。

    folder_id 唯一 → 必须复用既有行（含软删），不能新插，否则 unique 冲突。
    container→leaf：复用并重新激活（保留 current_value，只增不重置，Q230/Q251）。
    leaf→container：停用序列。
    """
    seq = _get_sequence_any(db, folder.id)
    if new_prefix:
        if seq is None:
            db.add(
                FolderSequence(
                    folder_id=folder.id,
                    current_value=0,
                    sequence_digits=sequence_digits or 5,
                )
            )
        else:
            seq.is_active = True
            seq.deleted_at = None
            if sequence_digits is not None:
                seq.sequence_digits = sequence_digits
    elif seq is not None and seq.is_active:
        seq.is_active = False
        seq.deleted_at = utcnow()
    db.flush()


def _assert_deletable(db: Session, folder: Folder) -> None:
    if folder.system:
        raise bad_request("FOLDER_SYSTEM_PROTECTED", "系统文件夹不可删除或修改")
    if _active_children(db, folder.id):
        raise bad_request("FOLDER_NOT_EMPTY", "文件夹含子文件夹，请先清空后再删除")
    if _has_active_procedures(db, folder.id):
        raise bad_request("FOLDER_NOT_EMPTY", "文件夹含程序，请先清空后再删除")


def _soft_delete(db: Session, folder: Folder) -> None:
    now = utcnow()
    folder.is_active = False
    folder.deleted_at = now
    seq = _get_active_sequence(db, folder.id)
    if seq is not None:
        seq.is_active = False
        seq.deleted_at = now
    db.flush()


def delete_folder(db: Session, folder_id: str, meta: RequestMeta) -> None:
    folder = _get(db, folder_id)
    _assert_deletable(db, folder)
    snapshot = _snapshot(folder)
    _soft_delete(db, folder)
    audit_service.log_folder_action(
        db, target_id=folder.id, action="delete", meta=meta, old_value=snapshot
    )


def batch_delete(db: Session, ids: list[str], meta: RequestMeta) -> BatchDeleteResult:
    """原子批量软删（Q20/Q325）：先全量校验，任一失败则全部不动并返回错误详情。"""
    seen: set[str] = set()
    unique_ids: list[str] = []
    for fid in ids:
        if fid not in seen:
            seen.add(fid)
            unique_ids.append(fid)

    failed: list[BatchDeleteFailure] = []
    targets: list[Folder] = []
    for fid in unique_ids:
        try:
            folder = _get(db, fid)
            _assert_deletable(db, folder)
        except HTTPException as exc:
            detail: dict[str, Any] = exc.detail if isinstance(exc.detail, dict) else {}
            failed.append(
                BatchDeleteFailure(
                    id=fid,
                    code=str(detail.get("code", "")),
                    message=str(detail.get("message", "")),
                )
            )
            continue
        targets.append(folder)

    if failed:
        # 一项失败全部回滚：此前未做任何变更，直接返回空成功列表
        return BatchDeleteResult(deleted_ids=[], failed=failed)

    deleted_ids: list[str] = []
    snapshots: dict[str, dict[str, Any]] = {}
    for folder in targets:
        snapshots[folder.id] = _snapshot(folder)
        _soft_delete(db, folder)
        deleted_ids.append(folder.id)

    # 批量动作记一条/项 batch_delete：new_value 含 {ids, count}（Q122/Q123）
    batch_value: dict[str, Any] = {"ids": deleted_ids, "count": len(deleted_ids)}
    for fid in deleted_ids:
        audit_service.log_folder_action(
            db,
            target_id=fid,
            action="batch_delete",
            meta=meta,
            old_value=snapshots[fid],
            new_value=batch_value,
        )
    return BatchDeleteResult(deleted_ids=deleted_ids, failed=[])


# --------------------------------------------------------------------------- #
# 读操作
# --------------------------------------------------------------------------- #
def get_folder(db: Session, folder_id: str) -> Folder:
    return _get(db, folder_id)


_SORTABLE = {"created_at": Folder.created_at, "updated_at": Folder.updated_at, "name": Folder.name}


def list_folders(
    db: Session, *, page: int, page_size: int, sort: str, search: str | None
) -> tuple[list[Folder], int]:
    stmt = select(Folder).where(Folder.is_active.is_(True))
    if search:
        for token in search.split():
            stmt = stmt.where(Folder.name.ilike(f"%{_like_escape(token)}%", escape="\\"))

    desc = sort.startswith("-")
    field = _SORTABLE.get(sort.lstrip("-"), Folder.created_at)
    stmt = stmt.order_by(field.desc() if desc else field.asc())

    total = db.execute(
        select(func.count()).select_from(stmt.order_by(None).subquery())
    ).scalar_one()
    rows = list(db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars())
    return rows, int(total)


def list_options(db: Session) -> list[Folder]:
    return list(
        db.execute(
            select(Folder).where(Folder.is_active.is_(True)).order_by(Folder.full_path)
        ).scalars()
    )


def get_tree(db: Session) -> list[dict[str, Any]]:
    folders = list(
        db.execute(select(Folder).where(Folder.is_active.is_(True)).order_by(Folder.name)).scalars()
    )
    # 计数口径与程序库列表对齐：仅 is_current 且非 DRAFT（草稿只在草稿箱可见，
    # 不计入文件夹「N 个程序」徽标；历史非当前版本亦不计）。普通文件夹即 PUBLISHED、
    # 系统文件夹（归档/废止）即 ARCHIVED，均与点击文件夹后列表所见一致。
    counts = {
        fid: int(n)
        for fid, n in db.execute(
            select(Procedure.folder_id, func.count())
            .where(
                Procedure.is_active.is_(True),
                Procedure.is_current.is_(True),
                Procedure.status != "DRAFT",
            )
            .group_by(Procedure.folder_id)
        ).all()
    }

    nodes: dict[str, dict[str, Any]] = {}
    for f in folders:
        nodes[f.id] = {
            "id": f.id,
            "name": f.name,
            "prefix": f.prefix,
            "parent_id": f.parent_id,
            "system": f.system,
            "full_path": f.full_path,
            "created_at": f.created_at,
            "updated_at": f.updated_at,
            "procedure_count": counts.get(f.id, 0),
            "children": [],
        }

    roots: list[dict[str, Any]] = []
    for f in folders:
        node = nodes[f.id]
        parent = nodes.get(f.parent_id) if f.parent_id else None
        if parent is not None:
            parent["children"].append(node)
        else:
            roots.append(node)
    return roots


def check_name(
    db: Session, parent_id: str | None, name: str, exclude_id: str | None = None
) -> bool:
    """名称是否可用（True = 可用）。"""
    return not _name_taken(db, parent_id, name.strip(), exclude_id=exclude_id)


def check_prefix(db: Session, prefix: str, exclude_id: str | None = None) -> bool:
    """前缀是否可用（True = 可用）。空前缀视为不适用→可用。"""
    cleaned = prefix.strip()
    if not cleaned:
        return True
    return not _prefix_in_use(db, cleaned, exclude_id=exclude_id)
