"""ResolverChain 行为契约（P4）。"""
from __future__ import annotations

from app.parser.resolvers import ResolverChain


def test_first_hit_wins() -> None:
    chain = ResolverChain([lambda: (2, "override"), lambda: (1, "synonym")])
    assert chain.resolve() == (2, "override")


def test_all_miss_returns_none_pair() -> None:
    chain = ResolverChain([lambda: None, lambda: None])
    assert chain.resolve() == (None, None)


def test_later_resolver_used_when_earlier_misses() -> None:
    chain = ResolverChain([lambda: None, lambda: (3, "based_on")])
    assert chain.resolve() == (3, "based_on")
