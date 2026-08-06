"""ORM models: SyntheticUser, Transaction, Alert."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    # Naive UTC on purpose — every timestamp in this project (SQLite/Postgres
    # columns, the synthetic generator, feature engineering's time-delta
    # math) is naive-but-UTC, and mixing in aware datetimes here would break
    # every comparison. `datetime.utcnow()` does the same thing but is
    # deprecated since 3.12.
    return datetime.now(UTC).replace(tzinfo=None)


class SyntheticUser(Base):
    """A synthetic account profile the simulator generates transactions for.

    Carries the "home" statistics (typical amount, home city, usual
    categories) that fraud scenarios deliberately violate — e.g. account
    takeover fires a transaction far outside `avg_amount`/`std_amount` from
    a city that isn't `home_city`.
    """

    __tablename__ = "synthetic_users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String)
    home_city: Mapped[str] = mapped_column(String)
    home_country: Mapped[str] = mapped_column(String, default="India")
    avg_amount: Mapped[float] = mapped_column(Float)
    std_amount: Mapped[float] = mapped_column(Float)
    usual_categories: Mapped[list] = mapped_column(JSON)  # list[str]
    usual_hours: Mapped[list] = mapped_column(
        JSON
    )  # list[int], hours of day user is normally active
    known_devices: Mapped[list] = mapped_column(JSON)  # list[str] device ids
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    transactions: Mapped[list[Transaction]] = relationship(back_populates="user")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("synthetic_users.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True, default=_now)

    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String, default="INR")
    channel: Mapped[str] = mapped_column(
        String
    )  # upi | card_present | card_not_present | netbanking
    merchant: Mapped[str] = mapped_column(String)
    merchant_category: Mapped[str] = mapped_column(String)
    city: Mapped[str] = mapped_column(String)
    country: Mapped[str] = mapped_column(String, default="India")
    device_id: Mapped[str] = mapped_column(String)
    is_new_device: Mapped[bool] = mapped_column(Boolean, default=False)

    # Ground truth — only known because this is a synthetic dataset. Used for
    # offline training/eval, never fed to the online feature vector (that
    # would be label leakage).
    fraud_scenario: Mapped[str | None] = mapped_column(String, nullable=True)
    is_fraud_label: Mapped[bool] = mapped_column(Boolean, default=False)

    # Filled in by the scorer at ingest time.
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    model_version: Mapped[str | None] = mapped_column(String, nullable=True)
    scoring_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    user: Mapped[SyntheticUser] = relationship(back_populates="transactions")
    alert: Mapped[Alert | None] = relationship(back_populates="transaction", uselist=False)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.id"), unique=True)
    user_id: Mapped[str] = mapped_column(String)
    risk_score: Mapped[float] = mapped_column(Float)
    top_reasons: Mapped[list] = mapped_column(JSON)  # list[{feature, shap_value, direction}]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    transaction: Mapped[Transaction] = relationship(back_populates="alert")
