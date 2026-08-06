"""Pydantic response/request schemas — kept separate from the ORM models
(app.models) so the API contract can evolve independently of storage."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    timestamp: datetime
    amount: float
    currency: str
    channel: str
    merchant: str
    merchant_category: str
    city: str
    country: str
    is_new_device: bool
    risk_score: float | None
    is_flagged: bool
    scoring_latency_ms: float | None


class ReasonCode(BaseModel):
    feature: str
    shap_value: float
    feature_value: float | str
    direction: str  # "increases_risk" | "decreases_risk"


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    transaction_id: str
    user_id: str
    risk_score: float
    top_reasons: list[ReasonCode]
    created_at: datetime


class ExplanationOut(BaseModel):
    transaction_id: str
    risk_score: float
    is_flagged: bool
    xgb_probability: float
    isolation_forest_score: float
    base_value: float
    reasons: list[ReasonCode]
    feature_vector: dict[str, float | str]


class MetricsOut(BaseModel):
    trained_at: str
    n_train: int
    n_test: int
    fraud_rate_test: float
    roc_auc: float
    pr_auc: float
    precision_at_threshold: float
    recall_at_threshold: float
    f1_at_threshold: float
    threshold: float
    confusion_matrix: dict[str, int]  # tp, fp, tn, fn
    roc_curve: dict[str, list[float]]  # fpr, tpr
    pr_curve: dict[str, list[float]]  # precision, recall
    feature_importance: list[dict[str, float | str]]  # [{feature, importance}]


class StreamStatus(BaseModel):
    running: bool
    rate_tps: float
    total_generated: int
    total_flagged: int


class StreamControl(BaseModel):
    rate_tps: float | None = None
