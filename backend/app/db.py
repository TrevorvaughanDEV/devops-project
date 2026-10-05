"""SQLite storage for login attempts and threat-intel lookups.

One connection is shared by the sensor (writes) and the API (reads). Every call is
short, so a lock is simpler and faster here than a connection pool.
"""

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from .shell import defang, defang_urls

SCHEMA = """
CREATE TABLE IF NOT EXISTS attempts (
    id        INTEGER PRIMARY KEY,
    ts        REAL    NOT NULL,
    ip        TEXT    NOT NULL,
    username  TEXT    NOT NULL,
    password  TEXT,
    method    TEXT    NOT NULL,
    client    TEXT,
    country   TEXT,
    country_name TEXT,
    city      TEXT,
    lat       REAL,
    lon       REAL,
    asn       INTEGER,
    org       TEXT
);
CREATE INDEX IF NOT EXISTS idx_attempts_ts ON attempts(ts);
CREATE INDEX IF NOT EXISTS idx_attempts_ip ON attempts(ip, ts);

-- Bots that got into the fake shell, and what they typed there
CREATE TABLE IF NOT EXISTS sessions (
    id        TEXT PRIMARY KEY,
    ts        REAL NOT NULL,
    ended     REAL,
    ip        TEXT NOT NULL,
    username  TEXT,
    password  TEXT,
    client    TEXT,
    commands  INTEGER NOT NULL DEFAULT 0,
    country   TEXT,
    country_name TEXT,
    city      TEXT,
    lat       REAL,
    lon       REAL,
    asn       INTEGER,
    org       TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_ts ON sessions(ts);
CREATE INDEX IF NOT EXISTS idx_sessions_ip ON sessions(ip);

CREATE TABLE IF NOT EXISTS commands (
    id       INTEGER PRIMARY KEY,
    session  TEXT NOT NULL,
    ts       REAL NOT NULL,
    ip       TEXT NOT NULL,
    command  TEXT NOT NULL,
    urls     TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_commands_session ON commands(session, id);
CREATE INDEX IF NOT EXISTS idx_commands_ts ON commands(ts);

CREATE TABLE IF NOT EXISTS intel (
    ip       TEXT PRIMARY KEY,
    fetched  REAL NOT NULL,
    score    INTEGER,
    reports  INTEGER,
    usage    TEXT,
    isp      TEXT,
    domain   TEXT
);
"""

# Columns a "top N" query may group by. Anything else is rejected, so user input
# never reaches the SQL text.
TOP_FIELDS = {
    "passwords": "password",
    "usernames": "username",
    "countries": "country",
    "orgs": "org",
    "clients": "client",
}

EVENT_COLUMNS = (
    "id, ts, ip, username, password, method, client, country, country_name, city, lat, lon, org,"
    " accepted"
)
GEO_COLUMNS = ("country", "country_name", "city", "lat", "lon", "asn", "org")


# Attempts made through the website's "try to break in" box are stored with
# method = 'web'. They show on the map and in the live log, but every statistic
# below excludes them, so the numbers describe bots, not curious visitors.


class Store:
    def __init__(self, path: Path | str):
        path = Path(path)
        if str(path) != ":memory:":
            path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")
        self._db.executescript(SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        cols = {r[1] for r in self._db.execute("PRAGMA table_info(attempts)")}
        if "accepted" not in cols:  # added with the fake shell
            self._db.execute("ALTER TABLE attempts ADD COLUMN accepted INTEGER NOT NULL DEFAULT 0")
            self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def query(self, sql: str, args: tuple = ()) -> list[dict[str, Any]]:
        """Read-only SQL for the insight and report builders (fixed SQL, bound args)."""
        return self._all(sql, args)

    def _all(self, sql: str, args: tuple = ()) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(r) for r in self._db.execute(sql, args).fetchall()]

    def _one(self, sql: str, args: tuple = ()) -> dict[str, Any] | None:
        rows = self._all(sql, args)
        return rows[0] if rows else None

    # --- writes -------------------------------------------------------------

    def add_attempt(self, event: dict[str, Any]) -> int:
        cols = (
            "ts", "ip", "username", "password", "method", "client",
            "country", "country_name", "city", "lat", "lon", "asn", "org", "accepted",
        )  # fmt: skip
        event.setdefault("accepted", 0)
        with self._lock:
            cur = self._db.execute(
                f"INSERT INTO attempts ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                tuple(event.get(c) for c in cols),
            )
            self._db.commit()
            return int(cur.lastrowid)

    def open_session(self, event: dict[str, Any]) -> None:
        cols = ("id", "ts", "ip", "username", "password", "client", *GEO_COLUMNS)
        with self._lock:
            self._db.execute(
                f"INSERT OR IGNORE INTO sessions ({', '.join(cols)})"
                f" VALUES ({', '.join('?' * len(cols))})",
                (event["session"], *(event.get(c) for c in cols[1:])),
            )
            self._db.commit()

    def add_command(self, event: dict[str, Any]) -> int:
        with self._lock:
            cur = self._db.execute(
                "INSERT INTO commands (session, ts, ip, command, urls) VALUES (?, ?, ?, ?, ?)",
                (event["session"], event["ts"], event["ip"], event["command"], event["urls"]),
            )
            self._db.execute(
                "UPDATE sessions SET commands = commands + 1, ended = ? WHERE id = ?",
                (event["ts"], event["session"]),
            )
            self._db.commit()
            return int(cur.lastrowid)

    def close_session(self, session: str, ts: float) -> None:
        with self._lock:
            self._db.execute("UPDATE sessions SET ended = ? WHERE id = ?", (ts, session))
            self._db.commit()

    def unlocated_ips(self, limit: int = 5000) -> list[str]:
        return [
            r["ip"]
            for r in self._all(
                "SELECT DISTINCT ip FROM attempts WHERE country IS NULL LIMIT ?", (limit,)
            )
        ]

    def set_location(self, ip: str, geo: dict[str, Any]) -> int:
        cols = ("country", "country_name", "city", "lat", "lon", "asn", "org")
        with self._lock:
            cur = self._db.execute(
                f"UPDATE attempts SET {', '.join(f'{c} = ?' for c in cols)}"
                " WHERE ip = ? AND country IS NULL",
                (*(geo.get(c) for c in cols), ip),
            )
            self._db.commit()
            return cur.rowcount

    def prune(self, older_than_days: int) -> int:
        cutoff = time.time() - older_than_days * 86400
        with self._lock:
            cur = self._db.execute("DELETE FROM attempts WHERE ts < ?", (cutoff,))
            self._db.execute("DELETE FROM commands WHERE ts < ?", (cutoff,))
            self._db.execute("DELETE FROM sessions WHERE ts < ?", (cutoff,))
            self._db.commit()
            return cur.rowcount

    def save_intel(self, ip: str, data: dict[str, Any]) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO intel (ip, fetched, score, reports, usage, isp, domain)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    ip, time.time(), data.get("score"), data.get("reports"),
                    data.get("usage"), data.get("isp"), data.get("domain"),
                ),
            )  # fmt: skip
            self._db.commit()

    # --- reads --------------------------------------------------------------

    def summary(self, hours: int = 24) -> dict[str, Any]:
        since = time.time() - hours * 3600
        window = self._one(
            "SELECT COUNT(*) AS attempts, COUNT(DISTINCT ip) AS ips,"
            " COUNT(DISTINCT country) AS countries FROM attempts WHERE ts >= ? AND method != 'web'",
            (since,),
        )
        total = self._one(
            "SELECT COUNT(*) AS n, MIN(ts) AS first FROM attempts WHERE method != 'web'"
        )
        last = self._one("SELECT ts FROM attempts WHERE method != 'web' ORDER BY id DESC LIMIT 1")
        return {
            "hours": hours,
            "attempts": window["attempts"],
            "ips": window["ips"],
            "countries": window["countries"],
            "total_attempts": total["n"],
            "first_seen": total["first"],
            "last_seen": last["ts"] if last else None,
        }

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._all(f"SELECT {EVENT_COLUMNS} FROM attempts ORDER BY id DESC LIMIT ?", (limit,))

    def top(self, kind: str, hours: int = 24, limit: int = 10) -> list[dict[str, Any]]:
        col = TOP_FIELDS[kind]
        since = time.time() - hours * 3600
        extra = ", MAX(country_name) AS label" if kind == "countries" else ""
        return self._all(
            f"SELECT {col} AS value, COUNT(*) AS count, COUNT(DISTINCT ip) AS ips{extra}"
            f" FROM attempts WHERE ts >= ? AND {col} IS NOT NULL AND method != 'web'"
            f" GROUP BY {col} ORDER BY count DESC LIMIT ?",
            (since, limit),
        )

    def map_points(self, hours: int = 24, limit: int = 400) -> list[dict[str, Any]]:
        since = time.time() - hours * 3600
        return self._all(
            "SELECT ip, MAX(lat) AS lat, MAX(lon) AS lon, MAX(country) AS country,"
            " MAX(city) AS city, COUNT(*) AS count, MAX(ts) AS last"
            " FROM attempts WHERE ts >= ? AND lat IS NOT NULL"
            " GROUP BY ip ORDER BY count DESC LIMIT ?",
            (since, limit),
        )

    def timeline(self, hours: int = 48) -> list[dict[str, Any]]:
        since = time.time() - hours * 3600
        return self._all(
            "SELECT CAST(ts / 3600 AS INTEGER) * 3600 AS hour, COUNT(*) AS count"
            " FROM attempts WHERE ts >= ? AND method != 'web' GROUP BY hour ORDER BY hour",
            (since,),
        )

    def heatmap(self, days: int = 30) -> list[dict[str, Any]]:
        """Attempts by weekday (0 = Monday) and hour, in UTC."""
        since = time.time() - days * 86400
        return self._all(
            "SELECT (CAST(strftime('%w', ts, 'unixepoch') AS INTEGER) + 6) % 7 AS weekday,"
            " CAST(strftime('%H', ts, 'unixepoch') AS INTEGER) AS hour, COUNT(*) AS count"
            " FROM attempts WHERE ts >= ? AND method != 'web' GROUP BY weekday, hour",
            (since,),
        )

    def ip_detail(self, ip: str) -> dict[str, Any] | None:
        base = self._one(
            "SELECT ip, COUNT(*) AS attempts, MIN(ts) AS first_seen, MAX(ts) AS last_seen,"
            " MAX(country) AS country, MAX(country_name) AS country_name, MAX(city) AS city,"
            " MAX(lat) AS lat, MAX(lon) AS lon, MAX(asn) AS asn, MAX(org) AS org"
            " FROM attempts WHERE ip = ?",
            (ip,),
        )
        if not base or not base["attempts"]:
            return None
        base["credentials"] = self._all(
            "SELECT username, password, COUNT(*) AS count FROM attempts WHERE ip = ?"
            " GROUP BY username, password ORDER BY count DESC, MAX(ts) DESC LIMIT 25",
            (ip,),
        )
        base["clients"] = [
            r["client"]
            for r in self._all(
                "SELECT DISTINCT client FROM attempts WHERE ip = ? AND client IS NOT NULL",
                (ip,),
            )
        ]
        base["sessions"] = self.sessions(ip=ip, limit=5)
        base["intel"] = self._one(
            "SELECT score, reports, usage, isp, domain, fetched FROM intel WHERE ip = ?", (ip,)
        )
        return base

    # --- the fake shell ---------------------------------------------------------

    def sessions(
        self, ip: str | None = None, limit: int = 10, since: float = 0, with_commands: bool = True
    ) -> list[dict[str, Any]]:
        """Most recent shell sessions that ran something, with their commands."""
        where, args = "WHERE commands > 0 AND ts >= ?", [since]
        if ip:
            where += " AND ip = ?"
            args.append(ip)
        rows = self._all(
            "SELECT id, ts, ended, ip, username, password, client, commands, country,"
            f" country_name, city, org FROM sessions {where} ORDER BY ts DESC LIMIT ?",
            (*args, limit),
        )
        if with_commands:
            for r in rows:
                r["log"] = [
                    defang_urls(c["command"])
                    for c in self._all(
                        "SELECT command FROM commands WHERE session = ? ORDER BY id LIMIT 40",
                        (r["id"],),
                    )
                ]
        return rows

    def shell_summary(self, days: int = 7) -> dict[str, Any]:
        since = time.time() - days * 86400
        s = self._one(
            "SELECT COUNT(*) AS logins, COUNT(DISTINCT ip) AS ips,"
            " SUM(commands > 0) AS active FROM sessions WHERE ts >= ?",
            (since,),
        )
        c = self._one("SELECT COUNT(*) AS n FROM commands WHERE ts >= ?", (since,))
        top = self._all(
            "SELECT command AS value, COUNT(*) AS count, COUNT(DISTINCT ip) AS ips"
            " FROM commands WHERE ts >= ? AND command NOT IN ('exit', 'logout')"
            " GROUP BY command ORDER BY count DESC LIMIT 10",
            (since,),
        )
        url_rows = self._all(
            "SELECT urls, ip, ts FROM commands WHERE ts >= ? AND urls != ''"
            " ORDER BY id DESC LIMIT 20000",
            (since,),
        )
        downloads: dict[str, dict[str, Any]] = {}
        for r in url_rows:
            for u in r["urls"].split():
                d = downloads.setdefault(u, {"url": u, "count": 0, "ips": set(), "last": 0})
                d["count"] += 1
                d["ips"].add(r["ip"])
                d["last"] = max(d["last"], r["ts"])
        dl = sorted(downloads.values(), key=lambda d: (-d["count"], -d["last"]))[:10]
        for t in top:
            t["value"] = defang_urls(t["value"])
        return {
            "days": days,
            "logins": s["logins"] or 0,
            "active": s["active"] or 0,
            "ips": s["ips"] or 0,
            "commands": c["n"],
            "top_commands": top,
            "downloads": [{**d, "url": defang(d["url"]), "ips": len(d["ips"])} for d in dl],
        }
