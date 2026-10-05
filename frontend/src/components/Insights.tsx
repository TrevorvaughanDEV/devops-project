import type { Insight } from "../api";

export function Insights({ items }: { items: Insight[] | null }) {
  if (!items || items.length === 0) return null;
  return (
    <section className="band insights" aria-labelledby="insights-title">
      <h2 id="insights-title">What the data says</h2>
      <p className="band-intro">Worked out from the past week of attacks and updated as they arrive.</p>
      <ul className="insight-list">
        {items.map((i) => (
          <li key={i.key}>
            <span className="insight-stat">{i.stat}</span>
            <p>{i.text}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
