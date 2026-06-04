"""防回归护栏：TEXT/JSON/BLOB 列不得带字面 server_default。

MySQL 对 TEXT/BLOB/JSON 列只接受表达式默认 `DEFAULT (<expr>)`，不接受字面
`DEFAULT '…'`（错误 1101）。SQLAlchemy 的 `server_default="…"`（裸字符串）发出的是
字面默认；必须改用 `server_default=sa.text("('')")` 这类带括号的表达式默认。

本测试遍历 `Base.metadata`，对任何 TEXT/JSON/BLOB 列若带 `server_default`，断言其
`arg` 是 `TextClause`（表达式）而非裸字符串字面，防止未来再引入会卡 MySQL bootstrap
的字面 TEXT 默认。
"""

from sqlalchemy.sql.elements import TextClause

from app.models import Base


def test_no_literal_server_default_on_text_json_columns():
    bad = []
    for t in Base.metadata.sorted_tables:
        for c in t.columns:
            tn = type(c.type).__name__.upper()
            if ("TEXT" in tn or "JSON" in tn or "BLOB" in tn) and c.server_default is not None:
                arg = getattr(c.server_default, "arg", None)
                if not isinstance(arg, TextClause):
                    bad.append(f"{t.name}.{c.name}")
    assert not bad, "TEXT/JSON 列须用表达式默认 sa.text(\"('')\")，以下仍为字面: " + str(bad)
