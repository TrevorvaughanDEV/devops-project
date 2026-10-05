import { useState } from "react";
import { post, type Attempt, type TryResult } from "../api";
import { num, place } from "../format";

type Props = { port: number | undefined; onAttempt: (a: Attempt) => void };

export function TryIt({ port, onAttempt }: Props) {
  const [username, setUsername] = useState("root");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<TryResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const command = `ssh -p ${port ?? 2222} root@${location.hostname}`;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await post<TryResult>("/api/try", { username, password });
      setResult(r);
      if (r.attempt) onAttempt(r.attempt);
      setPassword("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(command);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard blocked: the command is still visible to copy by hand */
    }
  }

  const a = result?.attempt;
  return (
    <section className="try" aria-labelledby="try-title">
      <div className="try-intro">
        <h2 id="try-title">Try to break in</h2>
        <p>
          Your guess is sent to the honeypot as a real SSH login, from this server, credited to you.
          This box always says no, even to the passwords that let bots in. Everything you type is shown
          publicly, so don't use a real password.
        </p>
      </div>

      <form className="try-form" onSubmit={submit}>
        <label>
          <span>Username</span>
          <input value={username} onChange={(e) => setUsername(e.target.value)} maxLength={32}
                 required autoComplete="off" spellCheck={false} />
        </label>
        <label>
          <span>Password</span>
          <input value={password} onChange={(e) => setPassword(e.target.value)} maxLength={64}
                 required autoComplete="off" spellCheck={false} placeholder="Your best guess" />
        </label>
        <button type="submit" disabled={busy}>{busy ? "Trying…" : "Try to log in"}</button>
      </form>

      <div className="try-result" aria-live="polite">
        {error && <p className="try-error">{error}</p>}
        {result && !error && (
          <p>
            <strong>Access denied.</strong>{" "}
            {a?.lat != null
              ? `Your attempt is on the map, flying in from ${place(a.city, a.country_name)}.`
              : "Your attempt is in the log; your location couldn't be placed on the map."}{" "}
            {result.shell
              ? "From a bot, that password would have opened the fake shell. "
              : ""}
            Bots made {num(result.bots_today)} attempts in the last 24 hours
            {result.shell ? "." : "; only the ones using the very worst passwords got in, and only to a fake shell."}
          </p>
        )}
      </div>

      <p className="try-cli">
        Prefer a terminal? <code>{command}</code>{" "}
        <button type="button" className="try-copy" onClick={copy}>{copied ? "Copied" : "Copy"}</button>
      </p>
    </section>
  );
}
