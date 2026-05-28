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


def enforce_node_invariants(
    kind: str,
    heading_level: int | None,
    input_schema: dict[str, Any] | None,
    attachment_marks: list[Any] | None,
) -> None:
    """ProcedureNode 写入硬约束(spec §1.3)——违反时 raise 422。

    1. kind='node' → input_schema 与 attachment_marks 必须为空(章节/正文不带表单)。
    2. kind='step' → heading_level 必须为 None(步骤是叶子表单,不能是标题)。
    3. heading_level 若非 None,必须是 >=1 的整数。
    """
    if heading_level is not None and (not isinstance(heading_level, int) or heading_level < 1):
        raise unprocessable(
            "NODE_INVARIANT",
            f"heading_level 必须是 >=1 的整数或 None(got {heading_level!r})",
            field="heading_level",
        )
    if kind == "step":
        if heading_level is not None:
            raise unprocessable(
                "NODE_INVARIANT",
                "kind='step' 不能带 heading_level(步骤不能是标题)",
                field="heading_level",
            )
        return
    # kind='node':无结构化字段
    schema_empty = input_schema is None or input_schema == {}
    marks_empty = attachment_marks is None or attachment_marks in ([], ())
    if not schema_empty:
        raise unprocessable(
            "NODE_INVARIANT",
            f"kind='node' 不应携带 input_schema(got {input_schema!r})",
            field="input_schema",
        )
    if not marks_empty:
        raise unprocessable(
            "NODE_INVARIANT",
            f"kind='node' 不应携带 attachment_marks(got {attachment_marks!r})",
            field="attachment_marks",
        )
