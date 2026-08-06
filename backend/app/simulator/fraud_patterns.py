"""Fraud scenario generators.

Each function takes a user profile (dict-like: id, home_city, avg_amount,
std_amount, usual_categories, known_devices) and a `now` timestamp, and
returns a list of transaction dicts — most scenarios are a single
transaction, "burst" scenarios (card testing, structuring) return several,
seconds-to-minutes apart, because the pattern only exists across multiple
events.

Detection of these patterns is NOT hardcoded here — that's the feature
engineering / model's job (see app/features/engineering.py). This module's
only responsibility is generating a believable *stimulus*; a transaction
tagged `fraud_scenario="impossible_travel"` is not, by itself, flagged
anywhere — it becomes suspicious only because the feature vector computed
from it and the user's recent history looks anomalous.
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta

from app.simulator.reference_data import (
    CHANNELS,
    CITIES_ANOMALOUS,
    HIGH_ABUSE_CATEGORIES,
    MERCHANT_CATEGORIES,
    MERCHANTS_BY_CATEGORY,
)

# Synthetic "reporting threshold" fraud actors structure transactions to stay
# under — mirrors real-world KYC/reporting limits without claiming to be one.
STRUCTURING_THRESHOLD = 50_000.0


def _pick_merchant(category: str) -> str:
    return random.choice(MERCHANTS_BY_CATEGORY[category])


def _new_device_id() -> str:
    return f"dev-{uuid.uuid4().hex[:10]}"


def _base_txn(user: dict, timestamp: datetime, **overrides) -> dict:
    # Default to *any* category, not a high-abuse one — a scenario should
    # have to opt in to the category signal explicitly (see
    # `card_testing_burst`/`structuring_burst`/`merchant_category_anomaly`
    # below). Defaulting to HIGH_ABUSE_CATEGORIES here would make
    # `is_high_abuse_category` a near-perfect predictor by construction,
    # which happened during development and produced a misleadingly clean
    # model — fraud that's realistically geo/velocity/device-driven
    # (account takeover, impossible travel) shouldn't also leak a category
    # tell for free.
    category = overrides.pop("merchant_category", random.choice(MERCHANT_CATEGORIES))
    txn = {
        "user_id": user["id"],
        "timestamp": timestamp,
        "amount": overrides.pop("amount", user["avg_amount"]),
        "currency": "INR",
        "channel": overrides.pop("channel", random.choice(CHANNELS)),
        "merchant_category": category,
        "merchant": _pick_merchant(category),
        "city": overrides.pop("city", user["home_city"]),
        "country": overrides.pop("country", "India"),
        "device_id": overrides.pop("device_id", random.choice(user["known_devices"])),
        "is_new_device": overrides.pop("is_new_device", False),
        "fraud_scenario": None,
        "is_fraud_label": True,
    }
    txn.update(overrides)
    return txn


def account_takeover(user: dict, now: datetime) -> list[dict]:
    """One large purchase from a brand-new device, in a city the account has
    never used, moments after (implied) credential compromise."""
    amount = user["avg_amount"] * random.uniform(5.0, 11.0) + user["std_amount"]
    txn = _base_txn(
        user,
        now,
        amount=round(amount, 2),
        channel=random.choice(["card_not_present", "netbanking"]),
        city=random.choice(CITIES_ANOMALOUS),
        country="Nigeria" if "Lagos" in CITIES_ANOMALOUS else "International",
        device_id=_new_device_id(),
        is_new_device=True,
        # Deliberately spans ALL categories, not just HIGH_ABUSE_CATEGORIES —
        # a hijacked account can be used to buy anything; the tell here is
        # the new device + unfamiliar city + amount spike, not the category.
        merchant_category=random.choice(MERCHANT_CATEGORIES),
    )
    txn["fraud_scenario"] = "account_takeover"
    return [txn]


def impossible_travel(user: dict, now: datetime) -> list[dict]:
    """A transaction from a city far from home, at an amount close to normal
    — the anomaly is purely geographic/velocity, not amount. Detection
    relies on comparing this against the user's actual previous transaction
    row, which the feature engineering step does."""
    amount = max(user["avg_amount"] + random.gauss(0, user["std_amount"] * 0.4), 10.0)
    txn = _base_txn(
        user,
        now,
        amount=round(amount, 2),
        channel="card_present",
        city=random.choice(CITIES_ANOMALOUS),
        country="International",
    )
    txn["fraud_scenario"] = "impossible_travel"
    return [txn]


def card_testing_burst(user: dict, now: datetime) -> list[dict]:
    """Several tiny, rapid-fire transactions — the classic pattern for
    validating a stolen card/UPI handle still works before a larger hit."""
    n = random.randint(4, 7)
    device = _new_device_id()
    txns = []
    t = now
    for _ in range(n):
        t = t + timedelta(seconds=random.uniform(2, 12))
        txn = _base_txn(
            user,
            t,
            amount=round(random.uniform(1, 99), 2),
            channel="card_not_present",
            device_id=device,
            is_new_device=True,
            merchant_category=random.choice(HIGH_ABUSE_CATEGORIES),
        )
        txn["fraud_scenario"] = "card_testing_burst"
        txns.append(txn)
    return txns


def structuring_burst(user: dict, now: datetime) -> list[dict]:
    """Multiple transactions each just under STRUCTURING_THRESHOLD, minutes
    apart, same category — splitting a large purchase to dodge a reporting
    limit."""
    n = random.randint(3, 4)
    category = random.choice(["jewellery", "electronics"])
    txns = []
    t = now
    for _ in range(n):
        t = t + timedelta(minutes=random.uniform(4, 20))
        amount = STRUCTURING_THRESHOLD * random.uniform(0.90, 0.99)
        txn = _base_txn(
            user,
            t,
            amount=round(amount, 2),
            channel=random.choice(["card_present", "netbanking"]),
            merchant_category=category,
        )
        txn["fraud_scenario"] = "structuring_burst"
        txns.append(txn)
    return txns


def merchant_category_anomaly(user: dict, now: datetime) -> list[dict]:
    """Amount looks totally normal — the only signal is a category the user
    has never touched, in the segment most associated with cash-out fraud."""
    unusual = [c for c in HIGH_ABUSE_CATEGORIES if c not in user["usual_categories"]]
    category = random.choice(unusual or HIGH_ABUSE_CATEGORIES)
    amount = max(user["avg_amount"] + random.gauss(0, user["std_amount"] * 0.3), 10.0)
    txn = _base_txn(
        user,
        now,
        amount=round(amount, 2),
        merchant_category=category,
    )
    txn["fraud_scenario"] = "merchant_category_anomaly"
    return [txn]


FRAUD_GENERATORS = {
    "account_takeover": account_takeover,
    "impossible_travel": impossible_travel,
    "card_testing_burst": card_testing_burst,
    "structuring_burst": structuring_burst,
    "merchant_category_anomaly": merchant_category_anomaly,
}

# Roughly weighted by real-world prevalence — category anomalies and card
# testing are common, full account takeover is rarer.
_SCENARIO_WEIGHTS = {
    "account_takeover": 0.15,
    "impossible_travel": 0.20,
    "card_testing_burst": 0.25,
    "structuring_burst": 0.15,
    "merchant_category_anomaly": 0.25,
}


def generate_fraud_sequence(user: dict, now: datetime) -> list[dict]:
    scenario = random.choices(
        list(_SCENARIO_WEIGHTS.keys()), weights=list(_SCENARIO_WEIGHTS.values())
    )[0]
    return FRAUD_GENERATORS[scenario](user, now)
