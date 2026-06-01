"""标题层级反查责任链（P4 重构，行为等价于原 classify_with_source）。

每个 Resolver 是一个可调用对象，命中返回 ``(level, source)``，不命中返回 ``None``
（→ 下一个）。Phase 2 的中心化分类器将作为新 Resolver 替换 HeuristicResolver 插槽，
不动其余环节。本模块只提供链容器；具体 resolver 由 styles.classify_with_source 内联
组装（捕获样式上下文的闭包），保持与原逻辑逐字节等价。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class ResolverChain:
    """按顺序求值的责任链：第一个返回非 None 的 resolver 获胜，全 miss 返回 (None, None)。"""

    resolvers: list[Callable[..., tuple[int, str] | None]]

    def resolve(self, *args, **kwargs) -> tuple[int | None, str | None]:
        for r in self.resolvers:
            hit = r(*args, **kwargs)
            if hit is not None:
                return hit
        return None, None
