"""SQLite storage for login attempts and threat-intel lookups.

One connection is shared by the sensor (writes) and the API (reads). Every call is
short, so a lock is simpler and faster here than a connection pool.
"""

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

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
    "id, ts, ip, username, password, method, client, country, country_name, city, lat, lon, org"
)


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

    def close(self) -> None:
        with self._lock:
            self._db.close()

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
            "country", "country_name", "city", "lat", "lon", "asn", "org",
        )  # fmt: skip
        with self._lock:
            cur = self._db.execute(
                f"INSERT INTO attempts ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                tuple(event.get(c) for c in cols),
            )
            self._db.commit()
            return int(cur.lastrowid)

    def prune(self, older_than_days: int) -> int:
        cutoff = time.time() - older_than_days * 86400
        with self._lock:
            cur = self._db.execute("DELETE FROM attempts WHERE ts < ?", (cutoff,))
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
            " COUNT(DISTINCT country) AS countries FROM attempts WHERE ts >= ?",
            (since,),
        )
        total = self._one("SELECT COUNT(*) AS n, MIN(ts) AS first FROM attempts")
        last = self._one("SELECT ts FROM attempts ORDER BY id DESC LIMIT 1")
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
            f" FROM attempts WHERE ts >= ? AND {col} IS NOT NULL"
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
            " FROM attempts WHERE ts >= ? GROUP BY hour ORDER BY hour",
            (since,),
        )

    def heatmap(self, days: int = 30) -> list[dict[str, Any]]:
        """Attempts by weekday (0 = Monday) and hour, in UTC."""
        since = time.time() - days * 86400
        return self._all(
            "SELECT (CAST(strftime('%w', ts, 'unixepoch') AS INTEGER) + 6) % 7 AS weekday,"
            " CAST(strftime('%H', ts, 'unixepoch') AS INTEGER) AS hour, COUNT(*) AS count"
            " FROM attempts WHERE ts >= ? GROUP BY weekday, hour",
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
        base["intel"] = self._one(
            "SELECT score, reports, usage, isp, domain, fetched FROM intel WHERE ip = ?", (ip,)
        )
        return base
