/** A single-series bar chart in plain SVG: thin bars with rounded tops on a quiet grid, a tooltip per bar, and
 * the numbers as a table for screen readers. One series, so no legend: the panel's title names it. */

import { useState } from "react";
import { formatDay } from "../../dashboard/table";

const W = 640, H = 220, PAD = { l: 36, r: 8, t: 12, b: 26 };

function niceMax(v: number) {
  const step = 10 ** Math.floor(Math.log10(Math.max(1, v)));
  return Math.ceil(v / step) * step;
}

export function BarChart({ data, label }: { data: { x: string; y: number }[]; label: string }) {
  const [hot, setHot] = useState<number | null>(null);
  const max = niceMax(Math.max(...data.map((d) => d.y), 1));
  const iw = W - PAD.l - PAD.r, ih = H - PAD.t - PAD.b;
  const slot = iw / data.length;
  const bw = Math.min(28, slot * 0.6);
  const y = (v: number) => PAD.t + ih - (v / max) * ih;
  const ticks = [0, max / 2, max];
  const short = (iso: string) => formatDay(iso).replace(/,? \d{4}$/, "");

  return (
    <figure className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label} onPointerLeave={() => setHot(null)}>
        {ticks.map((t) => (
          <g key={t}>
            <line className="grid-line" x1={PAD.l} x2={W - PAD.r} y1={y(t)} y2={y(t)} />
            <text className="axis" x={PAD.l - 8} y={y(t) + 4} textAnchor="end">{t}</text>
          </g>
        ))}
        {data.map((d, i) => {
          const x = PAD.l + i * slot + (slot - bw) / 2;
          const h = Math.max(0, y(0) - y(d.y));
          const r = Math.min(4, h, bw / 2);
          return (
            <g key={d.x} onPointerEnter={() => setHot(i)}>
              <rect className="hit" x={PAD.l + i * slot} y={PAD.t} width={slot} height={ih} />
              <path className={`bar-mark ${hot === null || hot === i ? "" : "dim"}`}
                    d={`M${x},${y(0)} V${y(d.y) + r} q0,-${r} ${r},-${r} H${x + bw - r} q${r},0 ${r},${r} V${y(0)} Z`} />
              {(i % 2 === data.length % 2 || i === data.length - 1) && (
                <text className="axis" x={x + bw / 2} y={H - 8} textAnchor="middle">{short(d.x)}</text>
              )}
            </g>
          );
        })}
      </svg>
      {hot !== null && (
        <div className="chart-tip" style={{ left: `${((PAD.l + (hot + 0.5) * slot) / W) * 100}%`, top: `${(y(data[hot].y) / H) * 100}%` }}>
          <span className="muted">Week of {formatDay(data[hot].x)}</span>
          <strong className="tabular">{data[hot].y.toLocaleString()} MQLs</strong>
        </div>
      )}
      <table className="sr-only">
        <caption>{label}</caption>
        <tbody>{data.map((d) => <tr key={d.x}><th>{d.x}</th><td>{d.y}</td></tr>)}</tbody>
      </table>
    </figure>
  );
}
