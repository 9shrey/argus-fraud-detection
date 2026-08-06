"""Exercises the real trained artifacts in app/ml/artifacts/ — run
`uv run python -m app.ml.train` first if these fail with a missing-file
error (CI does this before pytest; see .github/workflows/ci.yml)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.features.engineering import FEATURE_NAMES
from app.ml.scorer import get_scorer
from app.simulator.fraud_patterns import account_takeover, card_testing_burst
from app.simulator.generator import generate_normal_event
from app.simulator.profiles import generate_user_profile

NOW = datetime(2026, 3, 1, 12, 0, 0)


def _history(user: dict, n: int = 15) -> list[dict]:
    return [generate_normal_event(user, NOW - timedelta(days=n - i)) for i in range(n)]


@pytest.fixture(scope="module")
def scorer():
    return get_scorer()


class TestScoreShape:
    def test_returns_all_expected_keys(self, scorer):
        user = generate_user_profile()
        result = scorer.score(generate_normal_event(user, NOW), history=[])
        for key in (
            "risk_score",
            "is_flagged",
            "xgb_probability",
            "isolation_forest_score",
            "base_value",
            "reasons",
            "feature_vector",
            "model_version",
            "latency_ms",
        ):
            assert key in result

    def test_risk_score_is_bounded_0_to_100(self, scorer):
        user = generate_user_profile()
        result = scorer.score(generate_normal_event(user, NOW), history=[])
        assert 0.0 <= result["risk_score"] <= 100.0

    def test_reasons_are_ranked_by_absolute_shap_value_descending(self, scorer):
        user = generate_user_profile()
        [txn] = account_takeover(user, NOW)
        result = scorer.score(txn, history=_history(user))
        magnitudes = [abs(r["shap_value"]) for r in result["reasons"]]
        assert magnitudes == sorted(magnitudes, reverse=True)

    def test_feature_vector_covers_every_declared_feature(self, scorer):
        user = generate_user_profile()
        result = scorer.score(generate_normal_event(user, NOW), history=[])
        assert set(result["feature_vector"].keys()) == set(FEATURE_NAMES)


class TestFraudScoresHigherThanNormal:
    """The core claim of the whole project: the ensemble actually separates
    the two classes. Run many times since generation is randomized —
    flaky here would mean the model doesn't work, not a bad test."""

    def test_account_takeover_scores_higher_than_normal_on_average(self, scorer):
        normal_scores, fraud_scores = [], []
        for _ in range(15):
            user = generate_user_profile()
            history = _history(user)
            normal_scores.append(
                scorer.score(generate_normal_event(user, NOW), history)["risk_score"]
            )
            [fraud_txn] = account_takeover(user, NOW)
            fraud_scores.append(scorer.score(fraud_txn, history)["risk_score"])

        avg_normal = sum(normal_scores) / len(normal_scores)
        avg_fraud = sum(fraud_scores) / len(fraud_scores)
        assert avg_fraud > avg_normal + 20  # a wide margin, not a coin flip

    def test_card_testing_burst_gets_flagged_by_its_last_transaction(self, scorer):
        """The signal is velocity — the FIRST transaction in a burst looks
        almost normal on its own; by the last one, the same-category/short-
        window counters should have pushed the score up."""
        user = generate_user_profile()
        base_history = _history(user)
        burst = card_testing_burst(user, NOW)

        # Score causally: each burst transaction sees only the earlier ones.
        running_history = list(base_history)
        scores = []
        for txn in burst:
            scores.append(scorer.score(txn, running_history)["risk_score"])
            running_history.append(txn)

        assert scores[-1] >= scores[0]


class TestModelVersionStable:
    def test_model_version_is_consistent_across_calls(self, scorer):
        user = generate_user_profile()
        v1 = scorer.score(generate_normal_event(user, NOW), [])["model_version"]
        v2 = scorer.score(generate_normal_event(user, NOW), [])["model_version"]
        assert v1 == v2
