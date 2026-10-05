import { useEffect, useRef, useState } from "react";

export type Attempt = {
  id: number;
  ts: number;
  ip: string;
  username: string;
  password: string | null;
  method: "password" | "publickey" | "web";
  client: string | null;
  country: string | null;
  country_name: string | null;
  city: string | null;
  lat: number | null;
  lon: number | null;
  org: string | null;
};

export type Summary = {
  hours: number;
  attempts: number;
  ips: number;
  countries: number;
  total_attempts: number;
  first_seen: number | null;
  last_seen: number | null;
};

export type Meta = {
  server: { label: string; lat: number; lon: number };
  port: number;
  sensor_running: boolean;
  geo_enabled: boolean;
  intel_enabled: boolean;
  started: number;
  viewers: number;
};

export type Ranked = { value: string; count: number; ips?: number; label?: string };
export type MapPoint = {
  ip: string; lat: number; lon: number; country: string | null;
  city: string | null; count: number; last: number;
};
export type HeatCell = { weekday: number; hour: number; count: number };
export type HourCount = { hour: number; count: number };

export type IpDetail = {
  ip: string; attempts: number; first_seen: number; last_seen: number;
  country: string | null; country_name: string | null; city: string | null;
  lat: number | null; lon: number | null; asn: number | null; org: string | null;
  credentials: { username: string; password: string | null; count: number }[];
  clients: string[];
  intel: { score: number | null; reports: number | null; usage: string | null;
           isp: string | null; domain: string | null } | null;
};

export class ApiError extends Error {}

export async function get<T>(path: string): Promise<T> {
  const r = await fetch(path, { headers: { Accept: "application/json" } });
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new ApiError(body.detail ?? `Request failed (${r.status})`);
  }
  return r.json();
}

export async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    const detail = Array.isArray(data.detail) ? "Check the username and password and try again." : data.detail;
    throw new ApiError(detail ?? `Request failed (${r.status})`);
  }
  return data as T;
}

export type Insight = { key: string; stat: string; text: string };

export type Report = {
  days: number; start: number; end: number;
  current: { n: number; ips: number; countries: number };
  previous: { n: number; ips: number; countries: number };
  by_day: { day: string; count: number }[];
  passwords: Ranked[]; usernames: Ranked[]; countries: Ranked[]; orgs: Ranked[];
  top_attacker: { ip: string; count: number; country: string | null; cc: string | null; org: string | null } | null;
  insights: Insight[];
};

export type TryResult = { result: "denied"; attempt: Attempt | null; bots_today: number };

/** Fetch on mount and every `everyMs`; keeps the last good value on errors. */
export function usePoll<T>(path: string, everyMs: number, bump = 0) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    const load = () =>
      get<T>(path)
        .then((d) => alive && (setData(d), setError(null)))
        .catch((e: Error) => alive && setError(e.message));
    load();
    const t = setInterval(load, everyMs);
    return () => { alive = false; clearInterval(t); };
  }, [path, everyMs, bump]);
  return { data, error };
}

export type LiveState = "connecting" | "live" | "offline";

/** Subscribe to the live feed, reconnecting with backoff. */
export function useLive(onAttempt: (a: Attempt) => void) {
  const [state, setState] = useState<LiveState>("connecting");
  const cb = useRef(onAttempt);
  cb.current = onAttempt;

  useEffect(() => {
    let ws: WebSocket | null = null;
    let retry = 0;
    let timer: ReturnType<typeof setTimeout>;
    let closed = false;

    const connect = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${proto}://${location.host}/api/live`);
      ws.onopen = () => { retry = 0; setState("live"); };
      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data);
        if (msg.type === "attempt") cb.current(msg.data as Attempt);
      };
      ws.onclose = () => {
        if (closed) return;
        setState("offline");
        timer = setTimeout(connect, Math.min(30000, 1000 * 2 ** retry++));
      };
    };
    connect();
    return () => { closed = true; clearTimeout(timer); ws?.close(); };
  }, []);

  return state;
}
