import type { Campaign } from "../api";
import { ago, flag, num } from "../format";

type Props = { items: Campaign[] | null; onSelect: (ip: string) => void };

export function Campaigns({ items, onSelect }: Props) {
  return (
    <section id="botnets" className="band" aria-labelledby="botnets-title">
      <h2 id="botnets-title">Botnets: one list, many machines</h2>
      <p className="band-intro">
        Machines that work through the same password list, using the same software, are grouped together. Passwords
        every bot tries (like <code>123456</code>) are ignored, so each group is linked by the unusual ones. Botnets
        often split a list between their machines, so it only takes an overlap, not an exact match.
      </p>
      {!items ? (
        <p className="muted">Loading…</p>
      ) : items.length === 0 ? (
        <p className="muted">No coordinated groups spotted in the past week.</p>
      ) : (
        <ol className="campaigns">
          {items.slice(0, 4).map((c) => (
            <li key={c.id} className="campaign">
              <header>
                <h3>
                  <b>{num(c.ips)}</b> machines in <b>{num(c.n_countries)}</b>{" "}
                  {c.n_countries === 1 ? "country" : "countries"}
                </h3>
                <span className="muted small">
                  Group {c.id} · active {ago(c.first_seen)} to {ago(c.last_seen)}
                </span>
              </header>
              <dl className="campaign-facts">
                <div><dt>Attempts</dt><dd>{num(c.attempts)} <span className="muted">({c.share}% of all)</span></dd></div>
                <div><dt>Distinctive passwords</dt><dd>{num(c.list_size)}</dd></div>
                <div><dt>Software</dt><dd>{c.client?.replace("SSH-2.0-", "") ?? "Not reported"}</dd></div>
              </dl>
              <p className="campaign-label">The list they share</p>
              <ul className="chips">
                {c.signature.map((s) => (
                  <li key={`${s.username}/${s.password}`} title={`Tried by ${s.ips} of the ${c.ips} machines`}>
                    <code>{s.username} / {s.password || "(empty)"}</code>
                  </li>
                ))}
              </ul>
              <p className="campaign-where">
                {c.countries.map((x) => (
                  <span key={x.value} title={`${x.label}: ${x.count}`}>{flag(x.value)}</span>
                ))}
                {c.networks[0] && <span className="muted small"> Mostly {c.networks[0].value}</span>}
              </p>
              <p className="campaign-label">Machines</p>
              <ul className="chips">
                {c.members.map((m) => (
                  <li key={m.ip}>
                    <button type="button" onClick={() => onSelect(m.ip)}>
                      <span aria-hidden="true">{flag(m.country)}</span> {m.ip}
                    </button>
                  </li>
                ))}
                {c.ips > c.members.length && <li className="muted small">+{num(c.ips - c.members.length)} more</li>}
              </ul>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
