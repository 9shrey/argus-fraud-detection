"""Transaction generation — normal activity plus dispatch into fraud
scenarios. Used two ways:

- **Live stream** (`app/routers/stream.py`): one call per tick, `timestamp`
  is real "now", because a live dashboard showing synthetic-future
  timestamps would look broken.
- **Historical training set** (`app/ml/train.py`): `generate_historical_dataset`
  spans a synthetic date range with plausible per-user hour-of-day
  distributions, so the model has enough labeled history to learn from.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from app.simulator.fraud_patterns import generate_fraud_sequence
from app.simulator.reference_data import CHANNEL_WEIGHTS, CHANNELS, CITIES_HOME, MERCHANT_CATEGORIES

CATEGORY_DRIFT_PROB = 0.12  # chance a "normal" purchase is outside the user's usual categories
TRAVEL_DOMESTIC_PROB = 0.04  # chance a normal txn happens in a different (still domestic) city


def generate_normal_event(user: dict, timestamp: datetime) -> dict:
    if random.random() < CATEGORY_DRIFT_PROB:
        category = random.choice(MERCHANT_CATEGORIES)
    else:
        category = random.choice(user["usual_categories"])

    amount = max(random.gauss(user["avg_amount"], user["std_amount"]), 10.0)

    city = user["home_city"]
    if random.random() < TRAVEL_DOMESTIC_PROB:
        city = random.choice([c for c in CITIES_HOME if c != user["home_city"]])

    from app.simulator.fraud_patterns import (
        _pick_merchant,  # local import, avoids a cycle at module load
    )

    return {
        "user_id": user["id"],
        "timestamp": timestamp,
        "amount": round(amount, 2),
        "currency": "INR",
        "channel": random.choices(CHANNELS, weights=CHANNEL_WEIGHTS)[0],
        "merchant_category": category,
        "merchant": _pick_merchant(category),
        "city": city,
        "country": "India",
        "device_id": random.choice(user["known_devices"]),
        "is_new_device": False,
        "fraud_scenario": None,
        "is_fraud_label": False,
    }


def generate_live_tick(users: list[dict], now: datetime, fraud_rate: float) -> list[dict]:
    """One "tick" of the live stream: pick a random user, decide fraud vs
    normal, return the resulting transaction(s) (bursts return several)."""
    user = random.choice(users)
    if random.random() < fraud_rate:
        return generate_fraud_sequence(user, now)
    return [generate_normal_event(user, now)]


def _sample_hour(user: dict) -> int:
    if random.random() < 0.85 and user["usual_hours"]:
        return random.choice(user["usual_hours"])
    return random.randint(0, 23)


def generate_historical_dataset(
    users: list[dict],
    days: int = 45,
    avg_txns_per_user_per_day: float = 1.4,
    fraud_rate: float = 0.06,
    end: datetime | None = None,
) -> list[dict]:
    """Build a labeled dataset spanning `days` days ending at `end` (default:
    now). Used only for offline training/evaluation — never inserted as the
    live stream's history."""
    end = end or datetime.now(UTC).replace(tzinfo=None)  # naive UTC — see app/models.py::_now
    start = end - timedelta(days=days)

    events: list[dict] = []
    for user in users:
        for day_offset in range(days):
            day = start + timedelta(days=day_offset)
            n_today = max(0, round(random.gauss(avg_txns_per_user_per_day, 0.8)))
            for _ in range(n_today):
                if random.random() < fraud_rate:
                    hour = _sample_hour(user)
                    ts = day.replace(
                        hour=hour, minute=random.randint(0, 59), second=random.randint(0, 59)
                    )
                    events.extend(generate_fraud_sequence(user, ts))
                else:
                    hour = _sample_hour(user)
                    ts = day.replace(
                        hour=hour, minute=random.randint(0, 59), second=random.randint(0, 59)
                    )
                    events.append(generate_normal_event(user, ts))

    events.sort(key=lambda e: e["timestamp"])
    return events
