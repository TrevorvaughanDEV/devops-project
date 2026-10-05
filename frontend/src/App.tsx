import { useCallback, useEffect, useState } from "react";
import {
  get, useLive, usePoll,
  type Attempt, type HeatCell, type MapPoint, type Meta, type Ranked, type Summary,
} from "./api";
import { AttackMap, toArc, type Arc } from "./components/AttackMap";
import { Heatmap } from "./components/Heatmap";
import { HowItWorks } from "./components/HowItWorks";
import { IpPanel } from "./components/IpPanel";
import { Log } from "./components/Log";
import { RankList } from "./components/RankList";
import { TryIt } from "./components/TryIt";
import { ago, num } from "./format";

const LOG_SIZE = 60;
const MAX_ARCS = 24;
const ARC_MS = 3200;

const ipFromHash = () => {
  const m = location.hash.match(/^#ip=([0-9a-fA-F.:]+)$/);
  return m ? m[1] : null;
};

export default function App() {
  const meta = usePoll<Meta>("/api/meta", 60_000).data;
  const polledSummary = usePoll<Summary>("/api/summary?hours=24", 30_000).data;
  const polledPoints = usePoll<MapPoint[]>("/api/map?hours=24", 60_000).data;
  const passwords = usePoll<Ranked[]>("/api/top/passwords?hours=168&limit=10", 60_000).data;
  const usernames = usePoll<Ranked[]>("/api/top/usernames?hours=168&limit=10", 60_000).data;
  const clients = usePoll<Ranked[]>("/api/top/clients?hours=168&limit=6", 120_000).data;
  const countries = usePoll<Ranked[]>("/api/top/countries?hours=168&limit=10", 60_000).data;
  const orgs = usePoll<Ranked[]>("/api/top/orgs?hours=168&limit=10", 120_000).data;
  const heat = usePoll<HeatCell[]>("/api/heatmap?days=30", 300_000).data;

  const [log, setLog] = useState<Attempt[]>([]);
  const [arcs, setArcs] = useState<Arc[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [points, setPoints] = useState<MapPoint[]>([]);
  const [selected, setSelected] = useState<string | null>(ipFromHash);
  const [mine, setMine] = useState<Set<number>>(() => new Set());

  useEffect(() => { if (polledSummary) setSummary(polledSummary); }, [polledSummary]);
  useEffect(() => { if (polledPoints) setPoints(polledPoints); }, [polledPoints]);
  useEffect(() => { get<Attempt[]>(`/api/recent?limit=${LOG_SIZE}`).then(setLog, () => {}); }, []);

  useEffect(() => {
    const onHash = () => setSelected(ipFromHash());
    addEventListener("hashchange", onHash);
    return () => removeEventListener("hashchange", onHash);
  }, []);

  const select = useCallback((ip: string | null) => {
    history.replaceState(null, "", ip ? `#ip=${ip}` : location.pathname);
    setSelected(ip);
  }, []);

  const live = useLive(
    useCallback((a: Attempt) => {
      setLog((l) => [a, ...l].slice(0, LOG_SIZE));
      if (a.method !== "web") {
        setSummary((s) => s && { ...s, attempts: s.attempts + 1, total_attempts: s.total_attempts + 1, last_seen: a.ts });
      }
      const arc = toArc(a);
      if (!arc) return;
      setArcs((xs) => [...xs, arc].slice(-MAX_ARCS));
      setTimeout(() => setArcs((xs) => xs.filter((x) => x.key !== arc.key)), ARC_MS);
      setPoints((ps) => {
        const i = ps.findIndex((p) => p.ip === a.ip);
        if (i >= 0) {
          const next = ps.slice();
          next[i] = { ...ps[i], count: ps[i].count + 1, last: a.ts };
          return next;
        }
        return [...ps, { ip: a.ip, lat: a.lat!, lon: a.lon!, country: a.country, city: a.city, count: 1, last: a.ts }];
      });
    }, []),
  );

  // The visitor's own attempt: mark it, and make sure it is in the log and on the map
  // even if the live feed delivered it before this response arrived (or not at all).
  const onMine = useCallback((a: Attempt) => {
    setMine((m) => new Set(m).add(a.id));
    setLog((l) => (l.some((x) => x.id === a.id) ? l : [a, ...l].slice(0, LOG_SIZE)));
    const arc = toArc(a);
    if (arc) {
      setArcs((xs) => (xs.some((x) => x.key === arc.key) ? xs : [...xs, arc].slice(-MAX_ARCS)));
      setTimeout(() => setArcs((xs) => xs.filter((x) => x.key !== arc.key)), ARC_MS + 2000);
    }
  }, []);

  const s = summary;
  return (
    <>
      <header className="masthead">
        <div className="masthead-inner">
          <a className="wordmark" href="/">Who's knocking?</a>
          <nav aria-label="Sections">
            <a href="#tries">What they try</a>
            <a href="#where">Where from</a>
            <a href="#how">How it works</a>
            <a href="https://github.com/TrevorvaughanDEV/devops-project">Source on GitHub</a>
          </nav>
        </div>
      </header>

      <main>
        <section className="hero" aria-labelledby="hero-title">
          <div className="hero-text">
            <h1 id="hero-title">
              {s && s.attempts > 0 ? (
                <>
                  In the last 24 hours, <b>{num(s.ips)}</b> {s.ips === 1 ? "machine" : "machines"} from{" "}
                  <b>{num(s.countries)}</b> {s.countries === 1 ? "country" : "countries"} tried to break into my
                  server <b>{num(s.attempts)}</b> times.
                </>
              ) : (
                <>Bots try to break into every server on the internet. This one is watching them.</>
              )}
            </h1>
            <p className="lede">
              This is an SSH honeypot: a server left open on purpose{meta ? ` on port ${meta.port}` : ""}, which
              records the username and password of every login attempt and lets none of them in. Every dot on the
              map is a real machine. Click one to see what it tried.
            </p>
            <p className="hero-meta">
              {s?.last_seen ? `Last attempt ${ago(s.last_seen)}` : "Waiting for the first attempt"}
              {s ? `, ${num(s.total_attempts)} recorded in total.` : "."}
            </p>
          </div>

          <div className="hero-board">
            <AttackMap meta={meta} points={points} arcs={arcs} mine={mine} onSelect={select} />
            <Log entries={log} state={live} port={meta?.port} mine={mine} onSelect={select} />
          </div>
          <TryIt port={meta?.port} onAttempt={onMine} />
        </section>

        <section id="tries" className="band" aria-labelledby="tries-title">
          <h2 id="tries-title">What they try</h2>
          <p className="band-intro">
            The most common guesses over the past week. Almost all of it is automated: lists of default and leaked
            passwords tried against every address that answers.
          </p>
          <div className="ranks">
            <RankList title="Passwords" caption="Most tried, past 7 days" rows={passwords} kind="credential" empty="No passwords recorded yet." />
            <RankList title="Usernames" caption="Most tried, past 7 days" rows={usernames} kind="credential" empty="No usernames recorded yet." />
            <RankList title="SSH software" caption="What the bots identify as" rows={clients} kind="plain" empty="Nothing recorded yet." />
          </div>
        </section>

        <section id="where" className="band" aria-labelledby="where-title">
          <h2 id="where-title">Where they come from</h2>
          <p className="band-intro">
            Location is where the attacking machine sits, not where the person behind it is. Most are rented cloud
            servers or hijacked home devices.
          </p>
          <div className="ranks ranks-2">
            <RankList title="Countries" caption="Past 7 days" rows={countries} kind="country" empty="No locations yet." />
            <RankList title="Networks" caption="Who owns the attacking address" rows={orgs} kind="plain" empty="No networks yet." />
          </div>
          <h3 className="heat-title">When they come</h3>
          <Heatmap cells={heat} />
        </section>

        <section id="how" className="band" aria-labelledby="how-title">
          <h2 id="how-title">How it works</h2>
          <HowItWorks />
        </section>
      </main>

      <footer className="foot">
        <p>
          Built and run by <a href="https://www.linkedin.com/in/trevor-vaughan-1739912ab/">Trevor Vaughan</a>,
          Network Engineering student at TU Dublin.
        </p>
        <p className="muted small">
          <a href="https://db-ip.com">IP Geolocation by DB-IP</a>, licensed CC BY 4.0. Map data from Natural Earth.
          Addresses shown are machines that attempted unauthorised logins.
        </p>
      </footer>

      {selected && <IpPanel ip={selected} onClose={() => select(null)} />}
    </>
  );
}
