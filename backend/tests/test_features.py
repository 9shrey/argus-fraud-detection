from __future__ import annotations

from datetime import datetime, timedelta

from app.features.engineering import FEATURE_NAMES, compute_features, feature_vector_to_list


def _txn(**overrides) -> dict:
    base = {
        "amount": 500.0,
        "timestamp": datetime(2026, 1, 15, 12, 0, 0),
        "city": "Bengaluru",
        "merchant_category": "groceries",
        "channel": "upi",
        "is_new_device": False,
    }
    base.update(overrides)
    return base


class TestNoHistory:
    def test_zscore_is_neutral_with_no_history(self):
        feats = compute_features(_txn(), history=[])
        assert feats["amount_zscore_user"] == 0.0

    def test_hours_since_last_is_large_with_no_history(self):
        feats = compute_features(_txn(), history=[])
        assert feats["hours_since_last_txn"] > 24 * 7

    def test_new_city_flag_is_false_on_a_first_ever_transaction(self):
        # No history means "unknown", not "new" — a first-ever transaction
        # shouldn't be penalized as if it deviates from an established pattern.
        feats = compute_features(_txn(city="Timbuktu"), history=[])
        assert feats["is_new_city_for_user"] == 0.0


class TestAmountZscore:
    def test_amount_far_above_history_mean_has_high_positive_zscore(self):
        history = [
            _txn(amount=a, timestamp=datetime(2026, 1, 10, 9, i))
            for i, a in enumerate([480, 500, 520, 510])
        ]
        feats = compute_features(_txn(amount=5000.0), history=history)
        assert feats["amount_zscore_user"] > 5

    def test_amount_matching_history_mean_has_low_zscore(self):
        history = [
            _txn(amount=a, timestamp=datetime(2026, 1, 10, 9, i))
            for i, a in enumerate([480, 500, 520, 510])
        ]
        feats = compute_features(_txn(amount=502.0), history=history)
        assert abs(feats["amount_zscore_user"]) < 0.5


class TestVelocity:
    def test_txn_count_1h_only_counts_within_the_window(self):
        now = datetime(2026, 1, 15, 12, 0, 0)
        history = [
            _txn(timestamp=now - timedelta(minutes=10)),  # inside 1h
            _txn(timestamp=now - timedelta(minutes=50)),  # inside 1h
            _txn(timestamp=now - timedelta(hours=2)),  # outside 1h, inside 24h
            _txn(timestamp=now - timedelta(days=2)),  # outside both windows
        ]
        feats = compute_features(_txn(timestamp=now), history=history)
        assert feats["txn_count_1h"] == 2
        assert feats["txn_count_24h"] == 3

    def test_same_category_burst_count_ignores_other_categories(self):
        now = datetime(2026, 1, 15, 12, 0, 0)
        history = [
            _txn(timestamp=now - timedelta(minutes=5), merchant_category="gaming"),
            _txn(timestamp=now - timedelta(minutes=10), merchant_category="gaming"),
            _txn(timestamp=now - timedelta(minutes=5), merchant_category="groceries"),
        ]
        feats = compute_features(_txn(timestamp=now, merchant_category="gaming"), history=history)
        assert feats["same_category_burst_count_30m"] == 2


class TestImpossibleTravel:
    def test_fires_on_a_different_city_within_the_window(self):
        now = datetime(2026, 1, 15, 12, 0, 0)
        history = [_txn(city="Bengaluru", timestamp=now - timedelta(minutes=30))]
        feats = compute_features(_txn(city="Moscow", timestamp=now), history=history)
        assert feats["impossible_travel_flag"] == 1.0

    def test_does_not_fire_within_the_same_city(self):
        now = datetime(2026, 1, 15, 12, 0, 0)
        history = [_txn(city="Bengaluru", timestamp=now - timedelta(minutes=30))]
        feats = compute_features(_txn(city="Bengaluru", timestamp=now), history=history)
        assert feats["impossible_travel_flag"] == 0.0

    def test_does_not_fire_outside_the_window_even_in_a_different_city(self):
        now = datetime(2026, 1, 15, 12, 0, 0)
        history = [_txn(city="Bengaluru", timestamp=now - timedelta(hours=6))]
        feats = compute_features(_txn(city="Moscow", timestamp=now), history=history)
        assert feats["impossible_travel_flag"] == 0.0


class TestCategoryFrequency:
    def test_frequent_category_scores_high(self):
        history = [
            _txn(merchant_category="groceries", timestamp=datetime(2026, 1, i, 9))
            for i in range(1, 10)
        ]
        feats = compute_features(_txn(merchant_category="groceries"), history=history)
        assert feats["category_freq_user"] == 1.0

    def test_never_seen_category_scores_zero(self):
        history = [
            _txn(merchant_category="groceries", timestamp=datetime(2026, 1, i, 9))
            for i in range(1, 10)
        ]
        feats = compute_features(_txn(merchant_category="jewellery"), history=history)
        assert feats["category_freq_user"] == 0.0


class TestStructuring:
    def test_ratio_scales_with_amount(self):
        low = compute_features(_txn(amount=1000.0), history=[])
        high = compute_features(_txn(amount=49000.0), history=[])
        assert high["structuring_threshold_ratio"] > low["structuring_threshold_ratio"]


class TestFeatureVectorOrdering:
    def test_all_feature_names_present(self):
        feats = compute_features(_txn(), history=[])
        assert set(feats.keys()) == set(FEATURE_NAMES)

    def test_projection_matches_declared_order(self):
        feats = compute_features(_txn(), history=[])
        vec = feature_vector_to_list(feats)
        assert vec == [feats[name] for name in FEATURE_NAMES]
