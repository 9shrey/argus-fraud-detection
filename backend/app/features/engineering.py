"""Feature engineering — the single source of truth for turning
(transaction, user history) into the numeric vector the model sees.

The one rule that matters here: `compute_features` is called identically
from offline training (`app/ml/train.py`, history sliced from a pandas
DataFrame) and online scoring (`app/ml/scorer.py`, history queried from
Postgres/SQLite). Same function, same feature order, both paths — that's
what prevents train/serve skew. `history` must be every prior transaction
for this user, sorted ascending by timestamp, strictly before `txn`'s
timestamp (no leakage from the future or from the transaction itself).
"""

from __future__ import annotations

import math
from datetime import datetime

from app.simulator.fraud_patterns import STRUCTURING_THRESHOLD
from app.simulator.reference_data import HIGH_ABUSE_CATEGORIES

FEATURE_NAMES = [
    "amount",
    "amount_log",
    "amount_zscore_user",
    "hours_since_last_txn",
    "txn_count_1h",
    "txn_count_24h",
    "amount_sum_1h",
    "is_new_city_for_user",
    "impossible_travel_flag",
    "is_new_device",
    "category_freq_user",
    "is_high_abuse_category",
    "hour_sin",
    "hour_cos",
    "is_unusual_hour",
    "channel_is_card_not_present",
    "structuring_threshold_ratio",
    "same_category_burst_count_30m",
    "is_small_amount",
]

_IMPOSSIBLE_TRAVEL_WINDOW_HOURS = 2.0
_SMALL_AMOUNT_CUTOFF = 100.0
_NEUTRAL_CATEGORY_FREQ = 0.1  # prior used when the user has no history at all


def compute_features(txn: dict, history: list[dict]) -> dict[str, float]:
    """`txn`: dict with amount, timestamp, city, device_id, is_new_device,
    merchant_category, channel. `history`: prior transactions for the same
    user, ascending by timestamp, all strictly before `txn["timestamp"]`."""
    amount = float(txn["amount"])
    ts: datetime = txn["timestamp"]

    amounts = [h["amount"] for h in history]
    if amounts:
        mean_amt = sum(amounts) / len(amounts)
        var = sum((a - mean_amt) ** 2 for a in amounts) / len(amounts)
        std_amt = math.sqrt(var) or 1.0
        amount_zscore = (amount - mean_amt) / std_amt
    else:
        amount_zscore = 0.0

    last = history[-1] if history else None
    if last is not None:
        hours_since_last = max((ts - last["timestamp"]).total_seconds() / 3600.0, 0.0)
    else:
        hours_since_last = 720.0  # ~30 days: "no recent history" reads as low-velocity, not risky

    window_1h = [h for h in history if (ts - h["timestamp"]).total_seconds() <= 3600]
    window_24h = [h for h in history if (ts - h["timestamp"]).total_seconds() <= 86400]
    window_30m = [
        h
        for h in history
        if (ts - h["timestamp"]).total_seconds() <= 1800
        and h["merchant_category"] == txn["merchant_category"]
    ]

    seen_cities = {h["city"] for h in history}
    is_new_city = float(bool(history) and txn["city"] not in seen_cities)

    impossible_travel = 0.0
    if last is not None and last["city"] != txn["city"]:
        if (ts - last["timestamp"]).total_seconds() / 3600.0 <= _IMPOSSIBLE_TRAVEL_WINDOW_HOURS:
            impossible_travel = 1.0

    if history:
        same_category = sum(
            1 for h in history if h["merchant_category"] == txn["merchant_category"]
        )
        category_freq = same_category / len(history)
    else:
        category_freq = _NEUTRAL_CATEGORY_FREQ

    hour = ts.hour
    hour_sin = math.sin(2 * math.pi * hour / 24)
    hour_cos = math.cos(2 * math.pi * hour / 24)
    is_unusual_hour = float(hour < 5 or hour > 23)

    return {
        "amount": amount,
        "amount_log": math.log1p(amount),
        "amount_zscore_user": amount_zscore,
        "hours_since_last_txn": hours_since_last,
        "txn_count_1h": float(len(window_1h)),
        "txn_count_24h": float(len(window_24h)),
        "amount_sum_1h": float(sum(h["amount"] for h in window_1h)),
        "is_new_city_for_user": is_new_city,
        "impossible_travel_flag": impossible_travel,
        "is_new_device": float(bool(txn.get("is_new_device"))),
        "category_freq_user": category_freq,
        "is_high_abuse_category": float(txn["merchant_category"] in HIGH_ABUSE_CATEGORIES),
        "hour_sin": hour_sin,
        "hour_cos": hour_cos,
        "is_unusual_hour": is_unusual_hour,
        "channel_is_card_not_present": float(txn["channel"] == "card_not_present"),
        "structuring_threshold_ratio": amount / STRUCTURING_THRESHOLD,
        "same_category_burst_count_30m": float(len(window_30m)),
        "is_small_amount": float(amount < _SMALL_AMOUNT_CUTOFF),
    }


def feature_vector_to_list(features: dict[str, float]) -> list[float]:
    """Order-locked projection used right before handing features to the
    model — guards against a dict ever being passed in a different order."""
    return [features[name] for name in FEATURE_NAMES]
