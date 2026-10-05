import type { ShellSession } from "../api";

/** A session's commands drawn as a terminal transcript (commands only: we never
 *  replay the fake output, it would just be noise). */
export function Terminal({ session, live = false }: { session: ShellSession; live?: boolean }) {
  const user = session.username && /^[a-z_][a-z0-9_-]{0,31}$/.test(session.username) ? session.username : "root";
  const prompt = `${user}@srv-mad-01:~${user === "root" ? "#" : "$"}`;
  return (
    <div className="term" role="log" aria-label={`Commands sent by ${session.ip}`}>
      <ol className="term-lines">
        {session.log.map((c, i) => (
          <li key={i}>
            <span className="term-prompt" aria-hidden="true">{prompt} </span>
            <code className={c.startsWith("[tunnel") ? "term-tunnel" : undefined}>{c}</code>
          </li>
        ))}
        {live && (
          <li aria-hidden="true">
            <span className="term-prompt">{prompt} </span>
            <span className="term-cursor" />
          </li>
        )}
      </ol>
      {session.commands > session.log.length && (
        <p className="term-more">…and {session.commands - session.log.length} more</p>
      )}
    </div>
  );
}
