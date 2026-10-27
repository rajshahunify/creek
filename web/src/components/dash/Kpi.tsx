import type { Kpi as K } from "../../dashboard/types";

const fmt = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 });

/** One headline number and how it moved since last week. The arrow and the sign carry the direction, not the colour. */
export function Kpi({ kpi }: { kpi: K }) {
  const d = kpi.value - kpi.before;
  const pct = kpi.format === "pct";
  const change = pct ? `${fmt.format(Math.abs(d))} pts` : kpi.before ? `${fmt.format(Math.abs((d / kpi.before) * 100))}%` : fmt.format(Math.abs(d));
  return (
    <div className="kpi panel">
      <span className="kpi-label">{kpi.label}</span>
      <strong className="kpi-value tabular">{fmt.format(kpi.value)}{pct && "%"}</strong>
      <span className={`kpi-delta ${d > 0 ? "up" : d < 0 ? "down" : ""}`}>
        {d > 0 ? "▲" : d < 0 ? "▼" : "–"} {d ? change : "no change"} <span className="muted">vs last week</span>
      </span>
    </div>
  );
}
