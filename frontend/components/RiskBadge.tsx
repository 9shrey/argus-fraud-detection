import { riskBand } from "@/lib/types";

const LABEL: Record<string, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
  critical: "Critical",
};

export function RiskBadge({ score }: { score: number }) {
  const band = riskBand(score);
  return (
    <span className={`badge risk-${band}`}>
      <span className="badge-dot" />
      {LABEL[band]} · {score.toFixed(0)}
    </span>
  );
}
