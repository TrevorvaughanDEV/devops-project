import { useEffect, useRef, useState } from "react";
import { get, type IpDetail } from "../api";
import { dateTime, flag, num, place, shown } from "../format";

export function IpPanel({ ip, onClose }: { ip: string; onClose: () => void }) {
  const [data, setData] = useState<IpDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    ref.current?.showModal();
    setData(null);
    setError(null);
    get<IpDetail>(`/api/ip/${encodeURIComponent(ip)}`).then(setData, (e: Error) => setError(e.message));
  }, [ip]);

  const intel = data?.intel;

  return (
    <dialog ref={ref} className="panel" onClose={onClose} aria-labelledby="panel-title">
      <header className="panel-head">
        <h2 id="panel-title">
          <span aria-hidden="true">{flag(data?.country)}</span> {ip}
        </h2>
        <button type="button" className="panel-close" onClick={() => ref.current?.close()}>
          Close
        </button>
      </header>

      {error && <p className="panel-error">{error}</p>}
      {!data && !error && <p className="muted">Looking up this address…</p>}

      {data && (
        <>
          <dl className="panel-facts">
            <div><dt>Location</dt><dd>{place(data.city, data.country_name)}</dd></div>
            <div><dt>Network</dt><dd>{data.org ? `${data.org}${data.asn ? ` (AS${data.asn})` : ""}` : "Unknown"}</dd></div>
            <div><dt>Login attempts</dt><dd>{num(data.attempts)}</dd></div>
            <div><dt>First seen</dt><dd>{dateTime(data.first_seen)}</dd></div>
            <div><dt>Last seen</dt><dd>{dateTime(data.last_seen)}</dd></div>
            <div><dt>SSH software</dt><dd>{data.clients.length ? data.clients.join(", ") : "Not reported"}</dd></div>
          </dl>

          {intel && (
            <p className="panel-intel">
              AbuseIPDB confidence <strong>{intel.score ?? "–"}%</strong> from {num(intel.reports)} reports
              {intel.usage ? `, listed as ${intel.usage.toLowerCase()}` : ""}.
            </p>
          )}

          <h3>What it tried</h3>
          <table className="panel-creds">
            <thead><tr><th>Username</th><th>Password</th><th>Times</th></tr></thead>
            <tbody>
              {data.credentials.map((c, i) => (
                <tr key={i}>
                  <td><code>{c.username || "(empty)"}</code></td>
                  <td><code>{shown(c.password)}</code></td>
                  <td>{num(c.count)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted small">
            Check it elsewhere:{" "}
            <a href={`https://www.abuseipdb.com/check/${ip}`} target="_blank" rel="noreferrer">AbuseIPDB</a>,{" "}
            <a href={`https://www.shodan.io/host/${ip}`} target="_blank" rel="noreferrer">Shodan</a>,{" "}
            <a href={`https://viz.greynoise.io/ip/${ip}`} target="_blank" rel="noreferrer">GreyNoise</a>
          </p>
        </>
      )}
    </dialog>
  );
}
