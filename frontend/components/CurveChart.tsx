const WIDTH = 320;
const HEIGHT = 232;
const PAD_LEFT = 36;
const PAD_BOTTOM = 38;
const PAD_TOP = 12;
const PAD_RIGHT = 12;

const PLOT_W = WIDTH - PAD_LEFT - PAD_RIGHT;
const PLOT_H = HEIGHT - PAD_TOP - PAD_BOTTOM;

function toSvg(x: number, y: number) {
  return { x: PAD_LEFT + x * PLOT_W, y: PAD_TOP + (1 - y) * PLOT_H };
}

const TICKS = [0, 0.25, 0.5, 0.75, 1];

export function CurveChart({
  xs,
  ys,
  color,
  xLabel,
  yLabel,
  showDiagonal = false,
}: {
  xs: number[];
  ys: number[];
  color: string;
  xLabel: string;
  yLabel: string;
  showDiagonal?: boolean;
}) {
  const points = xs.map((x, i) => toSvg(x, ys[i] ?? 0));
  const linePath = points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");
  const areaPath =
    linePath +
    ` L ${points[points.length - 1]?.x ?? PAD_LEFT} ${PAD_TOP + PLOT_H} L ${PAD_LEFT} ${PAD_TOP + PLOT_H} Z`;
  const origin = toSvg(0, 0);
  const top = toSvg(0, 1);
  const rightBase = toSvg(1, 0);

  return (
    <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} width="100%" role="img" aria-label={`${yLabel} vs ${xLabel}`}>
      {/* gridlines */}
      {TICKS.map((t) => {
        const gy = toSvg(0, t).y;
        const gx = toSvg(t, 0).x;
        return (
          <g key={t}>
            <line x1={PAD_LEFT} y1={gy} x2={PAD_LEFT + PLOT_W} y2={gy} stroke="var(--gridline)" strokeWidth={1} />
            <line x1={gx} y1={PAD_TOP} x2={gx} y2={PAD_TOP + PLOT_H} stroke="var(--gridline)" strokeWidth={1} />
          </g>
        );
      })}

      {/* axes */}
      <line x1={origin.x} y1={top.y} x2={origin.x} y2={origin.y} stroke="var(--axis)" strokeWidth={1.5} />
      <line x1={origin.x} y1={origin.y} x2={rightBase.x} y2={origin.y} stroke="var(--axis)" strokeWidth={1.5} />

      {showDiagonal && (
        <line
          x1={origin.x}
          y1={origin.y}
          x2={rightBase.x}
          y2={top.y}
          stroke="var(--text-muted)"
          strokeWidth={1}
          strokeDasharray="3 4"
        />
      )}

      <path d={areaPath} fill={color} opacity={0.08} stroke="none" />
      <path d={linePath} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />

      {TICKS.map((t) => (
        <text
          key={`xt-${t}`}
          x={toSvg(t, 0).x}
          y={PAD_TOP + PLOT_H + 14}
          fontSize={9}
          fill="var(--text-muted)"
          textAnchor="middle"
        >
          {t}
        </text>
      ))}
      {TICKS.map((t) => (
        <text key={`yt-${t}`} x={PAD_LEFT - 8} y={toSvg(0, t).y + 3} fontSize={9} fill="var(--text-muted)" textAnchor="end">
          {t}
        </text>
      ))}

      <text
        x={PAD_LEFT + PLOT_W / 2}
        y={HEIGHT - 6}
        fontSize={10}
        fill="var(--text-secondary)"
        textAnchor="middle"
        fontWeight={600}
      >
        {xLabel}
      </text>
      <text
        x={-(PAD_TOP + PLOT_H / 2)}
        y={11}
        fontSize={10}
        fill="var(--text-secondary)"
        textAnchor="middle"
        fontWeight={600}
        transform="rotate(-90)"
      >
        {yLabel}
      </text>
    </svg>
  );
}
