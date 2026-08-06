"""Online scorer: loads the artifacts `app.ml.train` produced once at
startup, then scores individual transactions using the exact same
`compute_features` call training used — that parity is what prevents
train/serve skew.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shap
import xgboost as xgb

from app.config import settings
from app.features.engineering import FEATURE_NAMES, compute_features


class FraudScorer:
    """Loaded once (see `get_scorer`), reused for every request."""

    def __init__(self, artifacts_dir: str | None = None):
        self.artifacts_dir = Path(artifacts_dir or settings.model_artifacts_dir)
        self._load()

    def _load(self) -> None:
        booster = xgb.Booster()
        booster.load_model(str(self.artifacts_dir / "xgb_model.json"))
        self.booster = booster
        self.iso_forest = joblib.load(self.artifacts_dir / "isolation_forest.joblib")
        self.calibration = json.loads((self.artifacts_dir / "calibration.json").read_text())
        # TreeExplainer wraps the booster directly (no need for the sklearn
        # wrapper) — cheap to construct, so it's built once here rather than
        # per-request.
        self.explainer = shap.TreeExplainer(self.booster)

    @property
    def model_version(self) -> str:
        return self.calibration["model_version"]

    def score(self, txn: dict, history: list[dict]) -> dict:
        """`history` must be this transaction's user's prior transactions,
        ascending by timestamp, strictly before `txn["timestamp"]` — same
        contract as training's `compute_features` calls."""
        t0 = time.perf_counter()
        features = compute_features(txn, history)
        row = pd.DataFrame([features])[FEATURE_NAMES]

        dmatrix = xgb.DMatrix(row, feature_names=FEATURE_NAMES)
        xgb_proba = float(self.booster.predict(dmatrix)[0])

        iso_raw = float(-self.iso_forest.decision_function(row)[0])
        lo, hi = self.calibration["iso_score_min"], self.calibration["iso_score_max"]
        iso_norm = float(np.clip((iso_raw - lo) / max(hi - lo, 1e-9), 0.0, 1.0))

        hybrid = (
            self.calibration["xgb_weight"] * xgb_proba + self.calibration["iso_weight"] * iso_norm
        )
        risk_score = round(hybrid * 100, 2)

        # NOTE: SHAP explains the booster's raw (log-odds) output space by
        # default, not the post-sigmoid probability — standard practice for
        # tree-model explainability, but it's why these values won't sum
        # exactly to `xgb_proba`. Sign and relative magnitude are what
        # matter for "why was this flagged", which is what the UI shows.
        shap_values = self.explainer.shap_values(row)
        shap_row = shap_values[0] if shap_values.ndim == 2 else shap_values
        expected_value = self.explainer.expected_value
        base_value = float(np.ravel(expected_value)[0])

        # Rank by raw SHAP magnitude first (plain numpy floats — no dict/str
        # typing to fight mypy over), then build the reason dicts in that
        # already-sorted order.
        ranked = sorted(
            zip(FEATURE_NAMES, shap_row, strict=True), key=lambda pair: -abs(float(pair[1]))
        )
        reasons = [
            {
                "feature": name,
                "shap_value": round(float(val), 4),
                "feature_value": features[name],
                "direction": "increases_risk" if val > 0 else "decreases_risk",
            }
            for name, val in ranked[:6]
        ]

        latency_ms = (time.perf_counter() - t0) * 1000

        return {
            "risk_score": risk_score,
            "is_flagged": risk_score >= settings.risk_threshold,
            "xgb_probability": round(xgb_proba, 4),
            "isolation_forest_score": round(iso_norm, 4),
            "base_value": base_value,
            "reasons": reasons,
            "feature_vector": features,
            "model_version": self.model_version,
            "latency_ms": round(latency_ms, 3),
        }


_scorer: FraudScorer | None = None


def get_scorer() -> FraudScorer:
    global _scorer
    if _scorer is None:
        _scorer = FraudScorer()
    return _scorer


def reset_scorer_cache() -> None:
    """Test hook — forces the next `get_scorer()` to reload from disk."""
    global _scorer
    _scorer = None
