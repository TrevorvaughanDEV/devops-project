import { useCallback, useEffect, useRef, useState } from "react";
import {
  get, useLive, usePoll,
  type Attempt, type Campaign, type HeatCell, type Insight, type MapPoint, type Meta, type Ranked,
  type ShellCommand, type ShellData, type ShellSession, type Summary,
} from "./api";
import { Campaigns } from "./components/Campaigns";
import { Inside } from "./components/Inside";
import { About } from "./components/About";
import { Insights } from "./components/Insights";
import { useCountUp, useNow } from "./useCountUp";
import { useAmbient } from "./useAmbient";
import { AttackMap, toArc, type Arc } from "./components/AttackMap";
import { Heatmap } from "./components/Heatmap";
import { HowItWorks } from "./components/HowItWorks";
import { IpPanel } from "./components/IpPanel";
import { Log } from "./components/Log";
import { RankList } from "./components/RankList";
import { TryIt } from "./components/TryIt";
import { SiteHeader, type NavLink } from "./components/SiteHeader";
import { ago, num, place, shown } from "./format";

const NAV: NavLink[] = [
  { href: "#tries", label: "What they try" },
  { href: "#inside", label: "Once inside" },
  { href: "#where", label: "Where from" },
  { href: "#botnets", label: "Botnets" },
  { href: "/report", label: "Weekly report" },
  { href: "#about", label: "About me" },
];

const LOG_SIZE = 60;
const MAX_ARCS = 24;
const ARC_MS = 3200;

const ipFromHash = () => {
  const m = location.hash.match(/^#ip=([0-9a-fA-F.:]+)$/);
  return m ? m[1] : null;
};

export default function App() {
  useAmbient();
  const meta = usePoll<Meta>("/api/meta", 60_000).data;
  const polledSummary = usePoll<Summary>("/api/summary?hours=24", 30_000).data;
  const polledPoints = usePoll<MapPoint[]>("/api/map?hours=24", 60_000).data;
  const passwords = usePoll<Ranked[]>("/api/top/passwords?hours=168&limit=10", 60_000).data;
  const usernames = usePoll<Ranked[]>("/api/top/usernames?hours=168&limit=10", 60_000).data;
  const clients = usePoll<Ranked[]>("/api/top/clients?hours=168&limit=6", 120_000).data;
  const countries = usePoll<Ranked[]>("/api/top/countries?hours=168&limit=10", 60_000).data;
  const orgs = usePoll<Ranked[]>("/api/top/orgs?hours=168&limit=10", 120_000).data;
  const heat = usePoll<HeatCell[]>("/api/heatmap?days=30", 300_000).data;
  const insights = usePoll<Insight[]>("/api/insights?days=7", 120_000).data;
  const countries24 = usePoll<Ranked[]>("/api/top/countries?hours=24&limit=50", 60_000).data;
  const campaigns = usePoll<Campaign[]>("/api/campaigns", 300_000).data;
  const [shellBump, setShellBump] = useState(0);
  const polledShell = usePoll<ShellData>("/api/shell?days=7", 120_000, shellBump).data;
  const [shell, setShell] = useState<ShellData | null>(null);
  const [liveSession, setLiveSession] = useState<string | null>(null);
  useEffect(() => { if (polledShell) setShell(polledShell); }, [polledShell]);
  const shellRef = useRef(shell);
  shellRef.current = shell;
  const lastBump = useRef(0);

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
    useCallback((c: ShellCommand) => {
      // Append to the session if it's on screen; a new session needs a refetch.
      setLiveSession(c.session);
      if (!shellRef.current?.recent.some((s) => s.id === c.session)) {
        // New session: refetch, at most every few seconds while it types
        if (Date.now() - lastBump.current > 4000) {
          lastBump.current = Date.now();
          setTimeout(() => setShellBump((n) => n + 1), 1500);
        }
        return;
      }
      setShell((d) => {
        if (!d) return d;
        const i = d.recent.findIndex((s) => s.id === c.session);
        if (i < 0) return d;
        const recent = d.recent.slice();
        const s: ShellSession = recent[i];
        recent[i] = { ...s, commands: s.commands + 1, log: s.log.length < 40 ? [...s.log, c.command] : s.log };
        return { ...d, commands: d.commands + 1, recent };
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
  const attempts = useCountUp(s?.attempts);
  const ips = useCountUp(s?.ips);
  const nCountries = useCountUp(s?.countries);
  const now = useNow();
  const latestBot = log.find((a) => a.method !== "web");
  return (
    <>
      <SiteHeader links={NAV} />

      <main>
        <section className="hero" aria-labelledby="hero-title">
          <div className="hero-bg" aria-hidden="true"><span className="hero-grid" /><span className="hero-beam" /></div>
          <div className="hero-text">
            <h1 id="hero-title">
              {s && s.attempts > 0 ? (
                <>
                  In the last 24 hours, <b>{num(ips)}</b> {s.ips === 1 ? "machine" : "machines"} from{" "}
                  <b>{num(nCountries)}</b> {s.countries === 1 ? "country" : "countries"} tried to break into my
                  server <b>{num(attempts)}</b> times.
                </>
              ) : (
                <>Bots try to break into every server on the internet. This one is watching them.</>
              )}
            </h1>
            <p className="lede">
              This is an SSH honeypot: a server left open on purpose{meta ? ` on port ${meta.port}` : ""}, which
              records the username and password of every login attempt. The worst passwords "work" and open a fake
              terminal, so you can also see what bots do once they think they're in. Every dot on the map is a real
              machine. Click one to see what it tried.
            </p>
            <p className="hero-meta" aria-live="off">
              {latestBot ? (
                <>
                  Last attempt {ago(latestBot.ts, now)} from {place(latestBot.city, latestBot.country_name)}:{" "}
                  <code>{latestBot.username} / {latestBot.method === "publickey" ? "SSH key" : shown(latestBot.password)}</code>
                  . {s ? `${num(s.total_attempts)} recorded in total.` : ""}
                </>
              ) : (
                "Waiting for the first attempt."
              )}
            </p>
          </div>

          <div className="hero-board">
            <AttackMap meta={meta} points={points} arcs={arcs} mine={mine} countries={countries24 ?? []} onSelect={select} />
            <Log entries={log} state={live} port={meta?.port} mine={mine} onSelect={select} />
          </div>
          <TryIt port={meta?.port} onAttempt={onMine} />
        </section>

        <Insights items={insights} />

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

        <Inside data={shell} liveSession={liveSession} onSelect={select} />

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

        <Campaigns items={campaigns} onSelect={select} />

        <section id="how" className="band" aria-labelledby="how-title">
          <h2 id="how-title">How it works</h2>
          <HowItWorks />
        </section>

        <About />
      </main>

      <footer className="foot">
        <p className="muted small">
          <a href="https://db-ip.com">IP Geolocation by DB-IP</a>, licensed CC BY 4.0. Map data from Natural Earth.
          Addresses shown are machines that attempted unauthorised logins.
        </p>
      </footer>

      {selected && <IpPanel ip={selected} onClose={() => select(null)} />}
    </>
  );
}
