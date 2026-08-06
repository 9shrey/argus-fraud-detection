import { riskBand } from "@/lib/types";

const STATUS_HEX: Record<string, string> = {
  low: "var(--status-good)",
  medium: "var(--status-warning)",
  high: "var(--status-serious)",
  critical: "var(--status-critical)",
};

const CX = 100;
const CY = 96;
const R = 78;
const STROKE = 14;

function polar(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = ((angleDeg - 180) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

/** A 180 degree arc from `startPct` to `endPct` of the gauge's 0-100 range. */
function arcPath(startPct: number, endPct: number) {
  const startAngle = (startPct / 100) * 180;
  const endAngle = (endPct / 100) * 180;
  const start = polar(CX, CY, R, startAngle);
  const end = polar(CX, CY, R, endAngle);
  const largeArc = endAngle - startAngle > 180 ? 1 : 0;
  return `M ${start.x} ${start.y} A ${R} ${R} 0 ${largeArc} 1 ${end.x} ${end.y}`;
}

export function RiskGauge({ score }: { score: number | null }) {
  const value = score ?? 0;
  const band = score !== null ? riskBand(score) : null;
  const color = band ? STATUS_HEX[band] : "var(--text-muted)";

  return (
    <div className="gauge-wrap">
      <svg viewBox="0 0 200 118" width="220" height="130" role="img" aria-label="Latest risk score">
        <path
          d={arcPath(0, 100)}
          fill="none"
          stroke="var(--gridline)"
          strokeWidth={STROKE}
          strokeLinecap="round"
        />
        {score !== null && (
          <path
            d={arcPath(0, value)}
            fill="none"
            stroke={color}
            strokeWidth={STROKE}
            strokeLinecap="round"
          />
        )}
      </svg>
      <div className="gauge-value" style={{ color }}>
        {score !== null ? score.toFixed(0) : "—"}
      </div>
      <div className="gauge-caption">Latest risk score</div>
    </div>
  );
}
