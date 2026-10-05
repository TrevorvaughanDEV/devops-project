import type { Attempt, LiveState } from "../api";
import { clock, flag, shown } from "../format";

type Props = { entries: Attempt[]; state: LiveState; port: number | undefined; onSelect: (ip: string) => void };

const STATUS: Record<LiveState, string> = {
  connecting: "Connecting to the live feed",
  live: "Live",
  offline: "Reconnecting",
};

export function Log({ entries, state, port, onSelect }: Props) {
  return (
    <section className="log" aria-labelledby="log-title">
      <header className="log-head">
        <h2 id="log-title">Login attempts</h2>
        <span className={`live live-${state}`} role="status">
          <span className="live-dot" aria-hidden="true" />
          {STATUS[state]}
        </span>
      </header>
      {entries.length === 0 ? (
        <p className="log-empty">
          Nothing yet. Bots usually find a new server within the hour; this list fills in as they
          try to log in{port ? ` on port ${port}` : ""}.
        </p>
      ) : (
        <ol className="log-list" aria-live="off">
          {entries.map((e) => (
            <li key={e.id}>
              <button type="button" className="log-row" onClick={() => onSelect(e.ip)}>
                <time dateTime={new Date(e.ts * 1000).toISOString()}>{clock(e.ts)}</time>
                <span className="log-ip">
                  <span aria-hidden="true">{flag(e.country)}</span> {e.ip}
                </span>
                <code className="log-cred">
                  {e.username}
                  <span className="log-sep" aria-label="with password">/</span>
                  {e.method === "publickey" ? <em>SSH key</em> : shown(e.password)}
                </code>
              </button>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
