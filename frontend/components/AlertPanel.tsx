import Link from "next/link";
import type { Alert } from "@/lib/types";
import { RiskBadge } from "./RiskBadge";

export function AlertPanel({ alerts }: { alerts: Alert[] }) {
  if (alerts.length === 0) {
    return <div className="feed-empty">No alerts yet.</div>;
  }

  return (
    <div>
      {alerts.map((a) => {
        const topReason = a.top_reasons[0];
        return (
          <Link
            key={a.id ?? a.transaction_id}
            href={`/transactions/${a.transaction_id}`}
            className="feed-row"
            style={{
              textDecoration: "none",
              color: "inherit",
              gridTemplateColumns: "1fr auto",
            }}
          >
            <span className="feed-main">
              <div className="feed-merchant">
                {a.merchant ?? "Unknown merchant"}
                {a.city ? ` · ${a.city}` : ""}
              </div>
              <div className="feed-meta">
                {topReason
                  ? `${topReason.feature.replace(/_/g, " ")} ${
                      topReason.direction === "increases_risk" ? "↑" : "↓"
                    }`
                  : "—"}
              </div>
            </span>
            <RiskBadge score={a.risk_score} />
          </Link>
        );
      })}
    </div>
  );
}
