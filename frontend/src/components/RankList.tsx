import type { Ranked } from "../api";
import { flag, num } from "../format";

type Props = {
  title: string;
  caption: string;
  rows: Ranked[] | null;
  kind: "credential" | "country" | "plain";
  empty: string;
};

export function RankList({ title, caption, rows, kind, empty }: Props) {
  const max = Math.max(1, ...(rows ?? []).map((r) => r.count));
  return (
    <section className="rank" aria-label={title}>
      <h3>{title}</h3>
      <p className="rank-caption">{caption}</p>
      {!rows ? (
        <p className="muted">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="muted">{empty}</p>
      ) : (
        <table>
          <thead className="visually-hidden">
            <tr><th>{title}</th><th>Attempts</th></tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.value} title={`${num(r.count)} attempts from ${num(r.ips)} addresses`}>
                <th scope="row">
                  <span className="rank-bar" style={{ width: `${(r.count / max) * 100}%` }} aria-hidden="true" />
                  {kind === "country" ? (
                    <span className="rank-label">
                      <span aria-hidden="true">{flag(r.value)}</span> {r.label ?? r.value}
                    </span>
                  ) : kind === "credential" ? (
                    <code className="rank-label">{r.value === "" ? "(empty)" : r.value}</code>
                  ) : (
                    <span className="rank-label">{r.value}</span>
                  )}
                </th>
                <td>{num(r.count)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
