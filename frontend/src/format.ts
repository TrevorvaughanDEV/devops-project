const nf = new Intl.NumberFormat("en-IE");
export const num = (n: number | null | undefined) => (n == null ? "–" : nf.format(n));

export function ago(ts: number | null | undefined, now = Date.now() / 1000): string {
  if (!ts) return "never";
  const s = Math.max(0, Math.round(now - ts));
  if (s < 5) return "just now";
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86400)} d ago`;
}

export const clock = (ts: number) =>
  new Date(ts * 1000).toLocaleTimeString("en-IE", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

export const dateTime = (ts: number) =>
  new Date(ts * 1000).toLocaleString("en-IE", { dateStyle: "medium", timeStyle: "short" });

/** "IE" -> 🇮🇪 using regional indicator symbols. */
export function flag(code: string | null | undefined): string {
  if (!code || code.length !== 2) return "🏳️";
  return String.fromCodePoint(...[...code.toUpperCase()].map((c) => 0x1f1a5 + c.charCodeAt(0)));
}

export const place = (city: string | null, country: string | null) =>
  [city, country].filter(Boolean).join(", ") || "Unknown location";

/** Passwords are shown exactly, but empty ones need to be visible too. */
export const shown = (s: string | null | undefined) =>
  s == null ? "(key)" : s === "" ? "(empty)" : s;
