"""跨服务的共用 invariant 校验。

汇集所有"写 ProcedureNode 时必须满足的硬约束"，避免逻辑散落到各 service。
"""

from __future__ import annotations

from typing import Any

from app.errors import unprocessable


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
