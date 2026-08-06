export function FeatureImportanceChart({
  data,
  topN = 10,
}: {
  data: { feature: string; importance: number }[];
  topN?: number;
}) {
  const rows = data.slice(0, topN);
  const max = Math.max(...rows.map((r) => r.importance), 1e-9);

  return (
    <div>
      {rows.map((r) => (
        <div className="reason-bar-row" key={r.feature} title={`gain: ${r.importance.toFixed(2)}`}>
          <span className="muted" style={{ fontSize: 12 }}>
            {r.feature.replace(/_/g, " ")}
          </span>
          <div className="reason-bar-track">
            <div
              className="reason-bar-fill"
              style={{
                left: 0,
                width: `${(r.importance / max) * 100}%`,
                background: "var(--series-blue)",
              }}
            />
          </div>
          <span style={{ textAlign: "right", fontVariantNumeric: "tabular-nums", fontSize: 12 }}>
            {r.importance.toFixed(1)}
          </span>
        </div>
      ))}
    </div>
  );
}
