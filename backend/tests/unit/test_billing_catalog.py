"""三档 catalog 纯函数：生效解锁所购功能，失效降级到 free。"""

from app.billing.catalog import (
    PLAN_CATALOG,
    Feature,
    Plan,
    effective_features,
    effective_seat_limit,
)


def test_catalog_shape():
    assert PLAN_CATALOG[Plan.free].seat_limit == 3
    assert PLAN_CATALOG[Plan.free].features == frozenset()
    assert PLAN_CATALOG[Plan.pro].seat_limit == 15
    assert PLAN_CATALOG[Plan.enterprise].seat_limit is None
    pro_feats = PLAN_CATALOG[Plan.pro].features
    assert pro_feats == {
        Feature.preventive_maintenance,
        Feature.meters,
        Feature.purchasing,
        Feature.analytics,
        Feature.sop,
    }
    # enterprise 至少含 pro 全部
    assert pro_feats <= PLAN_CATALOG[Plan.enterprise].features


def test_effective_features_active_unlocks_plan():
    assert effective_features("pro", "active") == PLAN_CATALOG[Plan.pro].features
    assert effective_features("free", "active") == frozenset()
    assert effective_features("enterprise", "trialing") == PLAN_CATALOG[Plan.enterprise].features


def test_effective_features_inactive_downgrades_to_free():
    for status in ("past_due", "canceled", "suspended"):
        assert effective_features("pro", status) == frozenset()
        assert effective_features("enterprise", status) == frozenset()


def test_effective_seat_limit():
    assert effective_seat_limit("free", "active") == 3
    assert effective_seat_limit("pro", "active") == 15
    assert effective_seat_limit("enterprise", "active") is None
    # 失效降到 free=3
    assert effective_seat_limit("pro", "canceled") == 3
    assert effective_seat_limit("enterprise", "suspended") == 3


def test_unknown_or_null_plan_treated_as_free():
    assert effective_features(None, "active") == frozenset()
    assert effective_features("bogus", "active") == frozenset()
    assert effective_seat_limit(None, "active") == 3
