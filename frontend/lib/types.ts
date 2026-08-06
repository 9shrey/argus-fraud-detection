export interface Transaction {
  id: string;
  user_id: string;
  timestamp: string;
  amount: number;
  currency: string;
  channel: string;
  merchant: string;
  merchant_category: string;
  city: string;
  country: string;
  is_new_device: boolean;
  risk_score: number | null;
  is_flagged: boolean;
  scoring_latency_ms: number | null;
}

export interface ReasonCode {
  feature: string;
  shap_value: number;
  feature_value: number | string;
  direction: "increases_risk" | "decreases_risk";
}

export interface Alert {
  id: string;
  transaction_id: string;
  user_id: string;
  risk_score: number;
  top_reasons: ReasonCode[];
  created_at: string;
  amount: number | null;
  currency: string | null;
  merchant: string | null;
  merchant_category: string | null;
  city: string | null;
  channel: string | null;
}

export interface Explanation {
  transaction_id: string;
  risk_score: number;
  is_flagged: boolean;
  xgb_probability: number;
  isolation_forest_score: number;
  base_value: number;
  reasons: ReasonCode[];
  feature_vector: Record<string, number | string>;
}

export interface Metrics {
  trained_at: string;
  n_train: number;
  n_test: number;
  fraud_rate_test: number;
  roc_auc: number;
  pr_auc: number;
  precision_at_threshold: number;
  recall_at_threshold: number;
  f1_at_threshold: number;
  threshold: number;
  confusion_matrix: { tp: number; fp: number; tn: number; fn: number };
  roc_curve: { fpr: number[]; tpr: number[] };
  pr_curve: { precision: number[]; recall: number[] };
  feature_importance: { feature: string; importance: number }[];
}

export interface StreamStatus {
  running: boolean;
  rate_tps: number;
  total_generated: number;
  total_flagged: number;
}

/** A single message pushed over the /stream/ws WebSocket. */
export interface StreamEvent {
  type: "transaction";
  id: string;
  user_id: string;
  timestamp: string;
  amount: number;
  currency: string;
  channel: string;
  merchant: string;
  merchant_category: string;
  city: string;
  country: string;
  risk_score: number;
  is_flagged: boolean;
  alert?: { top_reasons: ReasonCode[] };
}

/** Risk bands used throughout the UI — mirrors the backend's status-color
 * intent (good/warning/serious/critical) rather than a raw 0-100 number. */
export type RiskBand = "low" | "medium" | "high" | "critical";

export function riskBand(score: number): RiskBand {
  if (score >= 85) return "critical";
  if (score >= 65) return "high";
  if (score >= 35) return "medium";
  return "low";
}
