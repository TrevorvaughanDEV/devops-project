import { useState } from "react";
import { usePoll, type Report as ReportData } from "../api";
import { flag, num } from "../format";
import { RankList } from "./RankList";

const fmtDay = (iso: string, opts: Intl.DateTimeFormatOptions) =>
  new Date(`${iso}T12:00:00Z`).toLocaleDateString("en-IE", opts);
const fmtTs = (ts: number) => new Date(ts * 1000).toLocaleDateString("en-IE", { day: "numeric", month: "long" });

function change(cur: number, prev: number): string {
  if (!prev) return "the first full week of data";
  if (cur > prev * 3) return `up from ${num(prev)} the week before`;
  const pct = Math.round(((cur - prev) / prev) * 100);
  if (pct === 0) return "the same as the week before";
  return `${Math.abs(pct)}% ${pct > 0 ? "more" : "fewer"} than the week before`;
}

function DayBars({ days }: { days: ReportData["by_day"] }) {
  const [hover, setHover] = useState<number | null>(null);
  const max = Math.max(1, ...days.map((d) => d.count));
  const W = 640, H = 200, gap = 10, bw = (W - gap * (days.length - 1)) / Math.max(1, days.length);
  const busiest = days.findIndex((d) => d.count === max);
  return (
    <figure className="daybars">
      <svg viewBox={`0 0 ${W} ${H + 28}`} role="img" aria-label="Attempts per day">
        <line x1={0} x2={W} y1={H} y2={H} className="daybars-base" />
        {days.map((d, i) => {
          const h = Math.max(2, (d.count / max) * (H - 24));
          const x = i * (bw + gap);
          return (
            <g key={d.day} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
              <rect x={x} y={0} width={bw} height={H} fill="transparent" />
              <path
                className={hover === i ? "daybars-bar is-hover" : "daybars-bar"}
                d={`M${x},${H} V${H - h + 4} q0,-4 4,-4 h${bw - 8} q4,0 4,4 V${H} Z`}
              />
              {(i === busiest || hover === i) && (
                <text x={x + bw / 2} y={H - h - 8} textAnchor="middle" className="daybars-value">
                  {num(d.count)}
                </text>
              )}
              <text x={x + bw / 2} y={H + 20} textAnchor="middle" className="daybars-label">
                {fmtDay(d.day, { weekday: "short" })}
              </text>
            </g>
          );
        })}
      </svg>
      <table className="visually-hidden">
        <caption>Attempts per day</caption>
        <tbody>
          {days.map((d) => (
            <tr key={d.day}><th>{d.day}</th><td>{d.count}</td></tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}

export function Report() {
  const { data: r, error } = usePoll<ReportData>("/api/report?days=7", 300_000);
  const [copied, setCopied] = useState(false);

  const share = async () => {
    try {
      await navigator.clipboard.writeText(location.href);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard blocked */
    }
  };

  return (
    <>
      <header className="masthead">
        <div className="masthead-inner">
          <a className="wordmark" href="/">Who's knocking?</a>
          <nav aria-label="Sections">
            <a href="/">Live map</a>
            <a href="/#about">About me</a>
            <a href="https://github.com/TrevorvaughanDEV/devops-project">Source on GitHub</a>
          </nav>
        </div>
      </header>
      <main className="report">
        {error && <p className="panel-error">Couldn't load the report: {error}</p>}
        {!r && !error && <p className="muted">Putting the report together…</p>}
        {r && (
          <>
            <p className="report-dates">{fmtTs(r.start)} to {fmtTs(r.end)}</p>
            <h1>This week on my honeypot</h1>
            {r.current.n === 0 ? (
              <p className="lede">No attacks recorded this week yet. Check back soon: they never take long.</p>
            ) : (
              <p className="lede report-lede">
                <b>{num(r.current.n)}</b> login attempts from <b>{num(r.current.ips)}</b> machines in{" "}
                <b>{num(r.current.countries)}</b> countries. That's {change(r.current.n, r.previous.n)}, and
                not one of them got in.
              </p>
            )}
            <button type="button" className="try-copy report-share" onClick={share}>
              {copied ? "Link copied" : "Copy link to this report"}
            </button>

            {r.by_day.length > 0 && (
              <section className="report-block">
                <h2>Attempts per day</h2>
                <DayBars days={r.by_day} />
              </section>
            )}

            {r.insights.length > 0 && (
              <section className="report-block">
                <h2>What stood out</h2>
                <ul className="insight-list">
                  {r.insights.map((i) => (
                    <li key={i.key}><span className="insight-stat">{i.stat}</span><p>{i.text}</p></li>
                  ))}
                </ul>
              </section>
            )}

            {r.current.n > 0 && (
              <section className="report-block">
                <h2>The top tens</h2>
                <div className="ranks ranks-2">
                  <RankList title="Passwords" caption="This week" rows={r.passwords} kind="credential" empty="None yet." />
                  <RankList title="Usernames" caption="This week" rows={r.usernames} kind="credential" empty="None yet." />
                  <RankList title="Countries" caption="This week" rows={r.countries} kind="country" empty="None yet." />
                  <RankList title="Networks" caption="This week" rows={r.orgs} kind="plain" empty="None yet." />
                </div>
              </section>
            )}

            {r.top_attacker && (
              <section className="report-block">
                <h2>Most persistent attacker</h2>
                <p className="report-attacker">
                  <a href={`/#ip=${r.top_attacker.ip}`}>
                    <span aria-hidden="true">{flag(r.top_attacker.cc)}</span> <code>{r.top_attacker.ip}</code>
                  </a>{" "}
                  tried <b>{num(r.top_attacker.count)}</b> times
                  {r.top_attacker.country ? ` from ${r.top_attacker.country}` : ""}
                  {r.top_attacker.org ? `, on a network owned by ${r.top_attacker.org}` : ""}.
                </p>
              </section>
            )}
          </>
        )}
      </main>
      <footer className="foot">
        <p>
          Written automatically from <a href="/">Who's Knocking?</a>, an SSH honeypot built and run by{" "}
          <a href="https://www.linkedin.com/in/trevor-vaughan-1739912ab/">Trevor Vaughan</a>.
        </p>
      </footer>
    </>
  );
}
