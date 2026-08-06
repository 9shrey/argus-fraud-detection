"""Offline training pipeline: synthetic historical data -> causal feature
vectors -> XGBoost + Isolation Forest ensemble -> evaluation -> saved
artifacts in `app/ml/artifacts/`.

Run from `backend/`: `uv run python -m app.ml.train`. Safe to re-run any
time the feature set or synthetic generators change — it's fully
deterministic (seeded) and takes well under a minute.
"""

from __future__ import annotations

import json
import random
import time
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)

from app.config import settings
from app.features.engineering import FEATURE_NAMES, compute_features
from app.simulator.generator import generate_historical_dataset
from app.simulator.profiles import generate_user_profiles

SEED = 42
N_TRAIN_USERS = 400
HISTORY_DAYS = 60
TRAIN_FRACTION = 0.8  # chronological split — train on the past, test on the future
XGB_WEIGHT = 0.75
ISO_WEIGHT = 0.25


def _build_feature_frame(events: list[dict]) -> pd.DataFrame:
    """Causal feature construction: for every event, `history` is only that
    same user's strictly-earlier events, accumulated as we walk forward in
    time. This is the exact same call (`compute_features`) the online
    scorer makes with a DB-queried history — the loop here is the only
    training-specific part."""
    per_user_history: dict[str, list[dict]] = {}
    rows = []
    for event in events:  # `events` is already sorted ascending by timestamp
        uid = event["user_id"]
        history = per_user_history.setdefault(uid, [])
        # Widened to `object`: this row mixes the float feature vector with
        # a label, scenario tag, and bookkeeping columns dropped again
        # before training (X_train/X_test project back down to FEATURE_NAMES).
        feats: dict[str, object] = dict(compute_features(event, history))
        feats["label"] = int(event["is_fraud_label"])
        feats["fraud_scenario"] = event.get("fraud_scenario")
        feats["timestamp"] = event["timestamp"]
        feats["user_id"] = uid
        rows.append(feats)
        history.append(event)
    return pd.DataFrame(rows)


def _downsample(*arrays: np.ndarray, n: int = 60) -> list[list[float]]:
    idx = np.linspace(0, len(arrays[0]) - 1, min(n, len(arrays[0]))).astype(int)
    return [a[idx].tolist() for a in arrays]


def main() -> None:
    random.seed(SEED)
    np.random.seed(SEED)
    t0 = time.time()

    print(f"Generating {N_TRAIN_USERS} synthetic user profiles...")
    users = generate_user_profiles(N_TRAIN_USERS)

    print(f"Generating {HISTORY_DAYS} days of synthetic transaction history...")
    events = generate_historical_dataset(
        users, days=HISTORY_DAYS, fraud_rate=settings.simulation_fraud_rate
    )
    fraud_n = sum(e["is_fraud_label"] for e in events)
    print(
        f"  {len(events)} events generated ({fraud_n} labeled fraud, {fraud_n / len(events):.2%})"
    )

    print("Computing causal feature vectors...")
    df = _build_feature_frame(events).sort_values("timestamp").reset_index(drop=True)

    split_idx = int(len(df) * TRAIN_FRACTION)
    train_df, test_df = df.iloc[:split_idx], df.iloc[split_idx:]
    X_train, y_train = train_df[FEATURE_NAMES], train_df["label"]
    X_test, y_test = test_df[FEATURE_NAMES], test_df["label"]
    print(
        f"  train={len(train_df)} ({y_train.mean():.2%} fraud), "
        f"test={len(test_df)} ({y_test.mean():.2%} fraud)"
    )

    # --- XGBoost classifier ------------------------------------------------
    scale_pos_weight = (y_train == 0).sum() / max((y_train == 1).sum(), 1)
    xgb_model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.85,
        colsample_bytree=0.85,
        scale_pos_weight=scale_pos_weight,
        eval_metric="aucpr",
        random_state=SEED,
        n_jobs=-1,
    )
    xgb_model.fit(X_train, y_train)
    booster = xgb_model.get_booster()
    xgb_test_proba = xgb_model.predict_proba(X_test)[:, 1]

    # --- Isolation Forest (unsupervised anomaly leg) ------------------------
    # Trained unsupervised on the mostly-normal training rows — the point of
    # the ensemble is that this leg can flag a shape of anomaly the
    # supervised model never saw labeled as fraud during training.
    iso_forest = IsolationForest(
        n_estimators=200,
        contamination=float(settings.simulation_fraud_rate),
        random_state=SEED,
        n_jobs=-1,
    )
    iso_forest.fit(X_train)
    # decision_function: higher = more normal. Flip + min-max normalize
    # (bounds fit on train only) so it composes with the XGBoost probability
    # on a comparable 0-1 scale.
    iso_train_scores = -iso_forest.decision_function(X_train)
    iso_lo, iso_hi = float(iso_train_scores.min()), float(iso_train_scores.max())
    iso_test_raw = -iso_forest.decision_function(X_test)
    iso_test_norm = np.clip((iso_test_raw - iso_lo) / max(iso_hi - iso_lo, 1e-9), 0.0, 1.0)

    hybrid_test = XGB_WEIGHT * xgb_test_proba + ISO_WEIGHT * iso_test_norm
    risk_score_test = hybrid_test * 100

    # --- Evaluation ----------------------------------------------------------
    threshold = settings.risk_threshold
    y_pred = (risk_score_test >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_test, y_pred, labels=[0, 1]).ravel()
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-9)

    fpr, tpr, _ = roc_curve(y_test, risk_score_test)
    prec_curve, rec_curve, _ = precision_recall_curve(y_test, risk_score_test)
    fpr_s, tpr_s = _downsample(fpr, tpr)
    prec_s, rec_s = _downsample(prec_curve, rec_curve)

    importance = booster.get_score(importance_type="gain")

    def _gain(name: str) -> float:
        # xgboost's stub types this as float | list[float] (multi-class
        # models can report per-class gain); this model is binary, so it's
        # always a plain float, but we still guard the shape defensively.
        raw = importance.get(name, 0.0)
        return float(raw[0] if isinstance(raw, list) else raw)

    ranked_features = sorted(FEATURE_NAMES, key=lambda f: -_gain(f))
    importance_list = [{"feature": f, "importance": round(_gain(f), 4)} for f in ranked_features]

    metrics = {
        "trained_at": datetime.now(UTC).isoformat(),
        "n_train": int(len(train_df)),
        "n_test": int(len(test_df)),
        "fraud_rate_test": float(y_test.mean()),
        "roc_auc": float(roc_auc_score(y_test, risk_score_test)),
        "pr_auc": float(average_precision_score(y_test, risk_score_test)),
        "precision_at_threshold": float(precision),
        "recall_at_threshold": float(recall),
        "f1_at_threshold": float(f1),
        "threshold": float(threshold),
        "confusion_matrix": {"tp": int(tp), "fp": int(fp), "tn": int(tn), "fn": int(fn)},
        "roc_curve": {"fpr": fpr_s, "tpr": tpr_s},
        "pr_curve": {"precision": prec_s, "recall": rec_s},
        "feature_importance": importance_list,
    }
    calibration = {
        "iso_score_min": iso_lo,
        "iso_score_max": iso_hi,
        "xgb_weight": XGB_WEIGHT,
        "iso_weight": ISO_WEIGHT,
        "model_version": datetime.now(UTC).strftime("v%Y%m%d-%H%M%S"),
    }

    out_dir = Path(settings.model_artifacts_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    booster.save_model(str(out_dir / "xgb_model.json"))
    joblib.dump(iso_forest, out_dir / "isolation_forest.joblib")
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
    (out_dir / "calibration.json").write_text(json.dumps(calibration, indent=2))

    print(
        f"\nROC-AUC={metrics['roc_auc']:.4f}  PR-AUC={metrics['pr_auc']:.4f}  "
        f"precision={precision:.3f}  recall={recall:.3f}  f1={f1:.3f}"
    )
    print(f"confusion matrix: tp={tp} fp={fp} tn={tn} fn={fn}")
    print(f"Artifacts written to {out_dir.resolve()} in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
