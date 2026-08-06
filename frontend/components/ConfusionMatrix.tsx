function Cell({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "good" | "bad";
}) {
  const color = tone === "good" ? "var(--status-good)" : "var(--status-critical)";
  return (
    <div
      style={{
        borderRadius: 8,
        padding: "16px 12px",
        textAlign: "center",
        background: `color-mix(in srgb, ${color} 10%, transparent)`,
        border: `1px solid color-mix(in srgb, ${color} 25%, transparent)`,
      }}
    >
      <div style={{ fontSize: 24, fontWeight: 700, color, fontVariantNumeric: "tabular-nums" }}>
        {value}
      </div>
      <div className="muted" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.03em" }}>
        {label}
      </div>
    </div>
  );
}

export function ConfusionMatrix({
  tp,
  fp,
  tn,
  fn,
}: {
  tp: number;
  fp: number;
  tn: number;
  fn: number;
}) {
  return (
    <div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "auto 1fr 1fr",
          gap: 8,
          fontSize: 11,
          color: "var(--text-muted)",
          marginBottom: 4,
        }}
      >
        <div />
        <div style={{ textAlign: "center" }}>Predicted fraud</div>
        <div style={{ textAlign: "center" }}>Predicted normal</div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "auto 1fr 1fr", gap: 8, alignItems: "center" }}>
        <div style={{ fontSize: 11, color: "var(--text-muted)", writingMode: "vertical-rl" }}>
          Actual fraud
        </div>
        <Cell label="True positive" value={tp} tone="good" />
        <Cell label="False negative" value={fn} tone="bad" />

        <div style={{ fontSize: 11, color: "var(--text-muted)", writingMode: "vertical-rl" }}>
          Actual normal
        </div>
        <Cell label="False positive" value={fp} tone="bad" />
        <Cell label="True negative" value={tn} tone="good" />
      </div>
    </div>
  );
}
