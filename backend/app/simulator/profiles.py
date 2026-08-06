"""Synthetic user-profile generation.

Each profile carries the "home" statistics that fraud scenarios deliberately
violate: a typical spend distribution, a home city, categories the user
actually shops in, hours they're normally active, and 1-2 known devices.
"""

from __future__ import annotations

import random
import uuid

from faker import Faker

from app.simulator.reference_data import CITIES_HOME, MERCHANT_CATEGORIES

fake = Faker()


def _new_device_id() -> str:
    return f"dev-{uuid.uuid4().hex[:10]}"


def generate_user_profile() -> dict:
    """Return a dict matching SyntheticUser's constructor fields."""
    avg_amount = round(
        random.lognormvariate(mu=6.5, sigma=0.9), 2
    )  # skews toward realistic INR amounts
    std_amount = round(avg_amount * random.uniform(0.25, 0.55), 2)

    n_categories = random.randint(2, 5)
    usual_categories = random.sample(MERCHANT_CATEGORIES, n_categories)

    # Most people transact in a handful of windows: morning, lunch, evening.
    windows = [range(7, 10), range(12, 15), range(17, 22)]
    usual_hours = sorted({h for w in random.sample(windows, k=random.randint(1, 3)) for h in w})

    n_devices = random.choices([1, 2], weights=[0.75, 0.25])[0]
    known_devices = [_new_device_id() for _ in range(n_devices)]

    return {
        "id": str(uuid.uuid4()),
        "name": fake.name(),
        "home_city": random.choice(CITIES_HOME),
        "home_country": "India",
        "avg_amount": avg_amount,
        "std_amount": max(std_amount, 10.0),
        "usual_categories": usual_categories,
        "usual_hours": usual_hours,
        "known_devices": known_devices,
    }


def generate_user_profiles(n: int) -> list[dict]:
    return [generate_user_profile() for _ in range(n)]
