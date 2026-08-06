"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Explanation, Transaction } from "@/lib/types";
import { RiskBadge } from "@/components/RiskBadge";
import { StatTile } from "@/components/StatTile";
import { ReasonWaterfall } from "@/components/ReasonWaterfall";

function formatAmount(amount: number, currency: string) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency }).format(amount);
}

export default function TransactionDetailPage() {
  const params = useParams<{ id: string }>();
  const [txn, setTxn] = useState<Transaction | null>(null);
  const [explanation, setExplanation] = useState<Explanation | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.transaction(params.id), api.explain(params.id)])
      .then(([t, e]) => {
        setTxn(t);
        setExplanation(e);
      })
      .catch(() => setError("Transaction not found."));
  }, [params.id]);

  if (error) {
    return (
      <div className="error-banner">
        {error} <Link href="/">Back to the live feed</Link>
      </div>
    );
  }

  if (!txn || !explanation) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div className="skeleton" style={{ height: 100 }} />
        <div className="skeleton" style={{ height: 240 }} />
      </div>
    );
  }

  const featureRows = Object.entries(explanation.feature_vector);

  return (
    <>
      <Link href="/" className="muted" style={{ fontSize: 12, textDecoration: "none" }}>
        ← Back to the live feed
      </Link>

      <div className="card" style={{ marginTop: 12, marginBottom: 20 }}>
        <div className="card-body">
          <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
            <div>
              <h1 style={{ fontSize: 20, margin: "0 0 4px" }}>{txn.merchant}</h1>
              <p className="muted" style={{ margin: 0, fontSize: 13 }}>
                {txn.merchant_category.replace(/_/g, " ")} · {txn.city}, {txn.country} ·{" "}
                {new Date(txn.timestamp).toLocaleString()}
              </p>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 22, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>
                {formatAmount(txn.amount, txn.currency)}
              </div>
              <div style={{ marginTop: 4 }}>
                <RiskBadge score={explanation.risk_score} />
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-3" style={{ marginBottom: 20 }}>
        <StatTile label="XGBoost probability" value={explanation.xgb_probability.toFixed(3)} />
        <StatTile label="Isolation Forest anomaly" value={explanation.isolation_forest_score.toFixed(3)} />
        <StatTile label="Channel" value={txn.channel.replace(/_/g, " ")} sub={txn.is_new_device ? "new device" : "known device"} />
      </div>

      <div className="grid grid-2" style={{ alignItems: "start" }}>
        <div className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">Why this score</h2>
              <p className="card-subtitle">Top SHAP contributions, ranked by magnitude</p>
            </div>
          </div>
          <div className="card-body">
            <ReasonWaterfall reasons={explanation.reasons} />
            <p className="muted" style={{ fontSize: 11, marginTop: 14 }}>
              SHAP explains the model&apos;s raw (log-odds) output, so these values won&apos;t sum
              exactly to the risk score above — sign and relative magnitude are what matter.
            </p>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">Feature vector</h2>
              <p className="card-subtitle">Exactly what the model saw for this transaction</p>
            </div>
          </div>
          <div className="card-body" style={{ maxHeight: 420, overflowY: "auto" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Feature</th>
                  <th>Value</th>
                </tr>
              </thead>
              <tbody>
                {featureRows.map(([name, value]) => (
                  <tr key={name}>
                    <td style={{ fontVariantNumeric: "initial" }}>{name.replace(/_/g, " ")}</td>
                    <td>{typeof value === "number" ? value.toFixed(3) : value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </>
  );
}
