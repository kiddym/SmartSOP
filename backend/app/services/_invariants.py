"""跨服务的共用 invariant 校验。

汇集所有"写 ProcedureStep 时必须满足的硬约束"，避免逻辑散落到各 service。
"""

from __future__ import annotations

from typing import Any

from app.errors import unprocessable


def enforce_content_kind_invariant(
    kind: str,
    input_schema: dict[str, Any] | None,
    attachment_marks: list[Any] | None,
) -> None:
    """content kind 必须无结构化字段——违反时 raise HTTPException(422)。

    commit 93d67c6 后 ProcedureStep.kind ∈ {"step", "content"} 同表共存，
    "content" 行的语义是"只有 title? + rich_content，不带 input_schema/attachment_marks"。
    本 helper 给所有写入 ProcedureStep 的 service 路径提供终态硬约束，
    防止任何路径写出非法行（commit 93d67c6 之前的 step_service create/update
    完全无 cleanup 即是 latent hole；本约束为 fail-fast 兜底）。

    None 与空集合视为等价（"未设置"即 OK）。
    """
    if kind != "content":
        return
    schema_empty = input_schema is None or input_schema == {}
    marks_empty = attachment_marks is None or attachment_marks == [] or attachment_marks == ()
    if not schema_empty:
        raise unprocessable(
            "CONTENT_KIND_INVARIANT",
            f"content kind 不应携带 input_schema（got {input_schema!r}）—— "
            "违反 commit 93d67c6 后的 step↔content 同表语义",
            field="input_schema",
        )
    if not marks_empty:
        raise unprocessable(
            "CONTENT_KIND_INVARIANT",
            f"content kind 不应携带 attachment_marks（got {attachment_marks!r}）—— "
            "违反 commit 93d67c6 后的 step↔content 同表语义",
            field="attachment_marks",
        )
