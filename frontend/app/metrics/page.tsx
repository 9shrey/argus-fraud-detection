"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Metrics } from "@/lib/types";
import { StatTile } from "@/components/StatTile";
import { CurveChart } from "@/components/CurveChart";
import { FeatureImportanceChart } from "@/components/FeatureImportanceChart";
import { ConfusionMatrix } from "@/components/ConfusionMatrix";

export default function MetricsPage() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .metrics()
      .then(setMetrics)
      .catch(() =>
        setError(
          "No trained model found. Run `uv run python -m app.ml.train` in backend/ and reload.",
        ),
      );
  }, []);

  if (error) {
    return <div className="error-banner">{error}</div>;
  }

  if (!metrics) {
    return (
      <div className="grid grid-stats">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="skeleton" style={{ height: 84 }} />
        ))}
      </div>
    );
  }

  return (
    <>
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ fontSize: 20, margin: "0 0 4px" }}>Model performance</h1>
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>
          Evaluated once, offline, on a chronological holdout split (trained on the earlier 80% of
          synthetic history, tested on the later 20% — never a random shuffle, which would leak
          future information into training). Trained {new Date(metrics.trained_at).toLocaleString()}
          .
        </p>
      </div>

      <div className="grid grid-stats" style={{ marginBottom: 20 }}>
        <StatTile label="ROC-AUC" value={metrics.roc_auc.toFixed(3)} />
        <StatTile label="PR-AUC" value={metrics.pr_auc.toFixed(3)} />
        <StatTile label="Precision" value={metrics.precision_at_threshold.toFixed(3)} sub={`@ threshold ${metrics.threshold}`} />
        <StatTile label="Recall" value={metrics.recall_at_threshold.toFixed(3)} sub={`@ threshold ${metrics.threshold}`} />
        <StatTile label="F1" value={metrics.f1_at_threshold.toFixed(3)} />
        <StatTile
          label="Test set"
          value={String(metrics.n_test)}
          sub={`${(metrics.fraud_rate_test * 100).toFixed(1)}% fraud`}
        />
      </div>

      <div className="grid grid-2" style={{ marginBottom: 20, alignItems: "start" }}>
        <div className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">ROC curve</h2>
              <p className="card-subtitle">True positive rate vs. false positive rate</p>
            </div>
          </div>
          <div className="card-body">
            <CurveChart
              xs={metrics.roc_curve.fpr}
              ys={metrics.roc_curve.tpr}
              color="var(--series-blue)"
              xLabel="False positive rate"
              yLabel="True positive rate"
              showDiagonal
            />
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">Precision–recall curve</h2>
              <p className="card-subtitle">More informative than ROC on an imbalanced class</p>
            </div>
          </div>
          <div className="card-body">
            <CurveChart
              xs={metrics.pr_curve.recall}
              ys={metrics.pr_curve.precision}
              color="var(--series-orange)"
              xLabel="Recall"
              yLabel="Precision"
            />
          </div>
        </div>
      </div>

      <div className="grid grid-2" style={{ alignItems: "start" }}>
        <div className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">Confusion matrix</h2>
              <p className="card-subtitle">At the {metrics.threshold}-point risk threshold</p>
            </div>
          </div>
          <div className="card-body">
            <ConfusionMatrix {...metrics.confusion_matrix} />
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">Feature importance</h2>
              <p className="card-subtitle">XGBoost gain, top 10 of {metrics.feature_importance.length} features</p>
            </div>
          </div>
          <div className="card-body">
            <FeatureImportanceChart data={metrics.feature_importance} />
          </div>
        </div>
      </div>

      <p className="muted" style={{ fontSize: 12, marginTop: 24 }}>
        Note: the synthetic fraud scenarios here are more separable than real-world fraud (real
        fraud rates are typically well under 1%, and the tells are subtler) — these numbers
        demonstrate the pipeline works end to end, not real-world performance.
      </p>
    </>
  );
}
