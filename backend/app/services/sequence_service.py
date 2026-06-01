"""序列取号服务。

next_value 在事务内对 (company_id, scope) 行加锁后原子自增（MySQL 用
SELECT ... FOR UPDATE；SQLite 串行化连接天然原子）。调用方在同一事务内
取号 + 写业务行 + 提交。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.sequence import Sequence


def next_value(db: Session, scope: str, company_id: str) -> int:
    """返回该租户该 scope 的下一个编号（从 1 起），并自增计数器。"""
    seq = db.execute(
        select(Sequence)
        .where(Sequence.company_id == company_id, Sequence.scope == scope)
        .with_for_update()
    ).scalar_one_or_none()
    if seq is None:
        seq = Sequence(scope=scope, next_val=1, company_id=company_id)
        db.add(seq)
        db.flush()
    value = seq.next_val
    seq.next_val = value + 1
    db.flush()
    return value


def format_custom_id(prefix: str, value: int, digits: int = 6) -> str:
    """A + 1 -> 'A000001'。"""
    return f"{prefix}{value:0{digits}d}"
