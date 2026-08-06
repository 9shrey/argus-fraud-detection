import Link from "next/link";
import type { StreamEvent } from "@/lib/types";
import { RiskBadge } from "./RiskBadge";

function formatTime(iso: string) {
  const d = new Date(iso);
  return d.toLocaleTimeString(undefined, { hour12: false });
}

function formatAmount(amount: number, currency: string) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(amount);
}

export function LiveFeed({ events }: { events: StreamEvent[] }) {
  if (events.length === 0) {
    return <div className="feed-empty">No transactions yet — start the simulation above.</div>;
  }

  return (
    <div>
      {events.map((e) => (
        <Link
          key={e.id}
          href={`/transactions/${e.id}`}
          className={`feed-row${e.is_flagged ? " flagged" : ""}`}
          style={{ textDecoration: "none", color: "inherit" }}
        >
          <span className="feed-time">{formatTime(e.timestamp)}</span>
          <span className="feed-main">
            <div className="feed-merchant">{e.merchant}</div>
            <div className="feed-meta">
              {e.merchant_category.replace("_", " ")} · {e.city} · {e.channel.replace(/_/g, " ")}
            </div>
          </span>
          <span className="feed-amount">{formatAmount(e.amount, e.currency)}</span>
          <RiskBadge score={e.risk_score} />
        </Link>
      ))}
    </div>
  );
}
