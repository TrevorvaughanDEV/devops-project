import { useState } from "react";
import type { HeatCell } from "../api";
import { num } from "../format";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const STEPS = 5;

export function Heatmap({ cells }: { cells: HeatCell[] | null }) {
  const [hover, setHover] = useState<HeatCell | null>(null);
  const grid = new Map((cells ?? []).map((c) => [`${c.weekday}-${c.hour}`, c.count]));
  const max = Math.max(0, ...(cells ?? []).map((c) => c.count));
  const step = (n: number) => (n === 0 || max === 0 ? 0 : Math.min(STEPS, Math.ceil((n / max) * STEPS)));

  return (
    <div className="heat">
      <table className="heat-grid" aria-label="Attempts by day of week and hour, UTC">
        <thead>
          <tr>
            <td />
            {Array.from({ length: 24 }, (_, h) => (
              <th key={h} scope="col">{h % 3 === 0 ? String(h).padStart(2, "0") : ""}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {DAYS.map((d, wd) => (
            <tr key={d}>
              <th scope="row">{d}</th>
              {Array.from({ length: 24 }, (_, h) => {
                const n = grid.get(`${wd}-${h}`) ?? 0;
                return (
                  <td
                    key={h}
                    className={`heat-cell s${step(n)}`}
                    onMouseEnter={() => setHover({ weekday: wd, hour: h, count: n })}
                    onMouseLeave={() => setHover(null)}
                  >
                    <span className="visually-hidden">{`${d} ${h}:00, ${n} attempts`}</span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="heat-readout" aria-live="polite">
        {hover
          ? `${DAYS[hover.weekday]} ${String(hover.hour).padStart(2, "0")}:00–${String(hover.hour).padStart(2, "0")}:59 UTC: ${num(hover.count)} attempts`
          : max
            ? `Darkest square: ${num(max)} attempts in one hour. Hover a square for its count.`
            : "No attempts recorded yet."}
      </p>
    </div>
  );
}
