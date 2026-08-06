import type { ReasonCode } from "@/lib/types";

/** Diverging bars around zero — SHAP contributions push the score up
 * (increases_risk, red) or down (decreases_risk, blue) from the model's
 * base rate. Blue<->red is this project's diverging pair throughout. */
export function ReasonWaterfall({ reasons }: { reasons: ReasonCode[] }) {
  const max = Math.max(...reasons.map((r) => Math.abs(r.shap_value)), 1e-9);

  return (
    <div>
      {reasons.map((r) => {
        const pct = (Math.abs(r.shap_value) / max) * 50; // half-track max
        const positive = r.direction === "increases_risk";
        const color = positive ? "var(--status-critical)" : "var(--series-blue)";
        return (
          <div key={r.feature} className="reason-bar-row" style={{ gridTemplateColumns: "170px 1fr 70px" }}>
            <span className="muted" style={{ fontSize: 12 }}>
              {r.feature.replace(/_/g, " ")}
            </span>
            <div className="reason-bar-track" style={{ background: "var(--gridline)" }}>
              <div
                style={{
                  position: "absolute",
                  left: "50%",
                  top: 0,
                  bottom: 0,
                  width: 1,
                  background: "var(--axis)",
                }}
              />
              <div
                className="reason-bar-fill"
                style={{
                  left: positive ? "50%" : `${50 - pct}%`,
                  width: `${pct}%`,
                  background: color,
                }}
              />
            </div>
            <span style={{ textAlign: "right", fontVariantNumeric: "tabular-nums", fontSize: 12, color }}>
              {positive ? "+" : ""}
              {r.shap_value.toFixed(2)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
