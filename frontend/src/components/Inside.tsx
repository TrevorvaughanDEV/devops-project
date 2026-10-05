import { useEffect, useState } from "react";
import type { ShellData } from "../api";
import { ago, flag, num, place, shown } from "../format";
import { RankList } from "./RankList";
import { Terminal } from "./Terminal";

type Props = { data: ShellData | null; liveSession: string | null; onSelect: (ip: string) => void };

export function Inside({ data, liveSession, onSelect }: Props) {
  const [picked, setPicked] = useState<string | null>(null);
  const sessions = data?.recent ?? [];
  // Follow the newest session until the visitor picks one themselves
  const current = sessions.find((s) => s.id === picked) ?? sessions[0];
  useEffect(() => {
    if (picked && !sessions.some((s) => s.id === picked)) setPicked(null);
  }, [sessions, picked]);

  return (
    <section id="inside" className="band" aria-labelledby="inside-title">
      <h2 id="inside-title">What they do once they're in</h2>
      <p className="band-intro">
        A handful of the most common passwords, like <code>123456</code> and <code>admin</code>, "work". The bot
        lands in a fake Ubuntu terminal that answers like the real thing, but nothing it types ever runs and nothing
        is ever downloaded. This is what they tried.
      </p>

      {!data ? (
        <p className="muted">Loading…</p>
      ) : data.logins === 0 ? (
        <p className="muted">No bot has made it into the fake shell this week yet. It usually takes a few hours.</p>
      ) : (
        <>
          <p className="inside-stats">
            Past {data.days} days: <b>{num(data.logins)}</b> bots got in, <b>{num(data.active)}</b> ran commands,{" "}
            <b>{num(data.commands)}</b> commands in total
            {data.downloads.length ? <>, <b>{num(data.downloads.reduce((n, d) => n + d.count, 0))}</b> download attempts</> : null}.
          </p>
          <div className="inside">
            <div className="inside-term">
              {sessions.length > 1 && (
                <div className="session-tabs" role="tablist" aria-label="Recent break-ins">
                  {sessions.map((s) => (
                    <button
                      key={s.id}
                      type="button"
                      role="tab"
                      aria-selected={s.id === current?.id}
                      className="session-tab"
                      onClick={() => setPicked(s.id)}
                    >
                      <span aria-hidden="true">{flag(s.country)}</span> {ago(s.ts)}
                      {s.id === liveSession && <span className="tag tag-live">Live</span>}
                    </button>
                  ))}
                </div>
              )}
              {current && (
                <>
                  <p className="session-head">
                    <button type="button" className="linkish" onClick={() => onSelect(current.ip)}>
                      {current.ip}
                    </button>{" "}
                    from {place(current.city, current.country_name)}, logged in as{" "}
                    <code>{current.username} / {shown(current.password)}</code>
                  </p>
                  <Terminal session={current} live={current.id === liveSession} />
                </>
              )}
              {!current && <p className="muted">Bots got in but haven't typed anything yet.</p>}
            </div>
            <div className="inside-side">
              <RankList
                title="Most run commands"
                caption={`Past ${data.days} days`}
                rows={data.top_commands}
                kind="command"
                empty="No commands yet."
              />
              <section className="rank" aria-labelledby="dl-title">
                <h3 id="dl-title">What they tried to download</h3>
                <p className="rank-caption">Never fetched. Addresses are defanged so they can't be clicked.</p>
                {data.downloads.length === 0 ? (
                  <p className="muted">No download attempts yet.</p>
                ) : (
                  <ul className="downloads">
                    {data.downloads.map((d) => (
                      <li key={d.url}>
                        <code>{d.url}</code>
                        <span className="muted small">
                          {num(d.count)}× from {num(d.ips)} {d.ips === 1 ? "address" : "addresses"}, {ago(d.last)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
