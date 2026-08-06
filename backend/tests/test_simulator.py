from __future__ import annotations

from datetime import datetime

from app.simulator.fraud_patterns import (
    STRUCTURING_THRESHOLD,
    account_takeover,
    card_testing_burst,
    generate_fraud_sequence,
    impossible_travel,
    merchant_category_anomaly,
    structuring_burst,
)
from app.simulator.generator import (
    generate_historical_dataset,
    generate_live_tick,
    generate_normal_event,
)
from app.simulator.profiles import generate_user_profile, generate_user_profiles
from app.simulator.reference_data import MERCHANT_CATEGORIES

NOW = datetime(2026, 2, 1, 15, 30, 0)


def _user(**overrides) -> dict:
    base = generate_user_profile()
    base.update(overrides)
    return base


class TestProfiles:
    def test_profile_has_all_required_fields(self):
        p = generate_user_profile()
        for key in (
            "id",
            "name",
            "home_city",
            "avg_amount",
            "std_amount",
            "usual_categories",
            "usual_hours",
            "known_devices",
        ):
            assert key in p

    def test_avg_and_std_amount_are_positive(self):
        for _ in range(20):
            p = generate_user_profile()
            assert p["avg_amount"] > 0
            assert p["std_amount"] > 0

    def test_usual_categories_are_a_subset_of_known_categories(self):
        p = generate_user_profile()
        assert set(p["usual_categories"]).issubset(set(MERCHANT_CATEGORIES))

    def test_generate_user_profiles_returns_unique_ids(self):
        profiles = generate_user_profiles(50)
        assert len({p["id"] for p in profiles}) == 50


class TestNormalEvent:
    def test_normal_event_is_not_labeled_fraud(self):
        user = _user()
        event = generate_normal_event(user, NOW)
        assert event["is_fraud_label"] is False
        assert event["fraud_scenario"] is None

    def test_normal_event_device_is_a_known_device(self):
        user = _user()
        event = generate_normal_event(user, NOW)
        assert event["device_id"] in user["known_devices"]


class TestFraudScenarios:
    def test_account_takeover_uses_a_new_device_and_anomalous_city(self):
        user = _user()
        [txn] = account_takeover(user, NOW)
        assert txn["is_fraud_label"] is True
        assert txn["fraud_scenario"] == "account_takeover"
        assert txn["is_new_device"] is True
        assert txn["device_id"] not in user["known_devices"]
        assert txn["city"] != user["home_city"]

    def test_account_takeover_amount_is_well_above_user_average(self):
        user = _user(avg_amount=1000.0, std_amount=200.0)
        [txn] = account_takeover(user, NOW)
        assert txn["amount"] > user["avg_amount"] * 3

    def test_impossible_travel_single_transaction_labeled_fraud(self):
        user = _user()
        [txn] = impossible_travel(user, NOW)
        assert txn["fraud_scenario"] == "impossible_travel"
        assert txn["is_fraud_label"] is True

    def test_card_testing_burst_produces_multiple_small_rapid_transactions(self):
        user = _user()
        txns = card_testing_burst(user, NOW)
        assert 4 <= len(txns) <= 7
        assert all(t["amount"] < 100 for t in txns)
        assert all(t["fraud_scenario"] == "card_testing_burst" for t in txns)
        # strictly increasing timestamps, all within the same burst window
        timestamps = [t["timestamp"] for t in txns]
        assert timestamps == sorted(timestamps)
        assert (timestamps[-1] - timestamps[0]).total_seconds() < 120

    def test_structuring_burst_stays_under_the_threshold(self):
        user = _user()
        txns = structuring_burst(user, NOW)
        assert len(txns) >= 3
        assert all(t["amount"] < STRUCTURING_THRESHOLD for t in txns)
        assert all(t["amount"] > STRUCTURING_THRESHOLD * 0.85 for t in txns)

    def test_merchant_category_anomaly_avoids_the_users_usual_categories(self):
        user = _user(usual_categories=["groceries", "fuel"])
        [txn] = merchant_category_anomaly(user, NOW)
        assert txn["merchant_category"] not in user["usual_categories"]

    def test_generate_fraud_sequence_always_returns_labeled_fraud(self):
        user = _user()
        for _ in range(30):
            txns = generate_fraud_sequence(user, NOW)
            assert all(t["is_fraud_label"] for t in txns)
            assert all(t["user_id"] == user["id"] for t in txns)


class TestLiveTickAndHistorical:
    def test_generate_live_tick_returns_at_least_one_event(self):
        users = generate_user_profiles(10)
        events = generate_live_tick(users, NOW, fraud_rate=0.5)
        assert len(events) >= 1

    def test_generate_live_tick_zero_fraud_rate_never_labels_fraud(self):
        users = generate_user_profiles(10)
        for _ in range(20):
            events = generate_live_tick(users, NOW, fraud_rate=0.0)
            assert all(not e["is_fraud_label"] for e in events)

    def test_historical_dataset_is_sorted_and_has_both_classes(self):
        users = generate_user_profiles(20)
        events = generate_historical_dataset(users, days=10, fraud_rate=0.1, end=NOW)
        timestamps = [e["timestamp"] for e in events]
        assert timestamps == sorted(timestamps)
        labels = {e["is_fraud_label"] for e in events}
        assert labels == {True, False}
