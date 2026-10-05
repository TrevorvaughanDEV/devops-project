"""Plain-English findings from the attack data, and the weekly report.

Everything here counts bots only (method != 'web'), over a window ending now.
"""

import re
import time
from typing import Any

from .db import Store

BOTS = "method != 'web'"
# Networks that rent out servers. Most attacks come from machines like these,
# either rented by attackers or rented by someone careless and then hijacked.
CLOUD = re.compile(
    r"amazon|aws|google|microsoft|azure|digitalocean|ovh|hetzner|linode|akamai|vultr|"
    r"tencent|alibaba|huawei cloud|oracle|contabo|scaleway|ionos|choopa|leaseweb|"
    r"hostinger|m247|datacamp|cloud|hosting|server|data ?cent",
    re.I,
)
MIN_ATTEMPTS = 20


def _pct(part: float, whole: float) -> int:
    return round(100 * part / whole) if whole else 0


def _every(seconds: float) -> str:
    if seconds < 1:
        return f"{round(1 / seconds)} attempts every second"
    if seconds < 90:
        return f"one attempt every {round(seconds)} seconds"
    if seconds < 5400:
        return f"one attempt every {round(seconds / 60)} minutes"
    return f"one attempt every {round(seconds / 3600)} hours"


def _window(store: Store, since: float, until: float) -> dict[str, Any]:
    row = store.query(
        f"SELECT COUNT(*) AS n, COUNT(DISTINCT ip) AS ips, COUNT(DISTINCT country) AS countries,"
        f" MIN(ts) AS first FROM attempts WHERE {BOTS} AND ts >= ? AND ts < ?",
        (since, until),
    )[0]
    return row


def build(store: Store, days: int = 7, now: float | None = None) -> list[dict[str, str]]:
    now = time.time() if now is None else now
    since = now - days * 86400
    w = _window(store, since, now)
    n = w["n"]
    if n < MIN_ATTEMPTS:
        return []
    args = (since, now)
    where = f"WHERE {BOTS} AND ts >= ? AND ts < ?"
    out: list[dict[str, str]] = []

    span = max(60.0, now - max(since, w["first"]))
    out.append({
        "key": "rate",
        "stat": f"{n / (span / 3600):,.0f}/h",
        "text": f"Bots try to log in around the clock: {_every(span / n)} on average.",
    })  # fmt: skip

    root = store.query(f"SELECT COUNT(*) AS c FROM attempts {where} AND username = 'root'", args)
    root_pct = _pct(root[0]["c"], n)
    if root_pct:
        out.append({
            "key": "root",
            "stat": f"{root_pct}%",
            "text": f"{root_pct}% of attempts go straight for root, "
                    "the all-powerful admin account.",
        })  # fmt: skip

    top_pw = store.query(
        f"SELECT password, COUNT(*) AS c FROM attempts {where} AND password IS NOT NULL"
        " GROUP BY password ORDER BY c DESC LIMIT 10",
        args,
    )
    if top_pw:
        share = _pct(sum(r["c"] for r in top_pw), n)
        best = top_pw[0]["password"] or "(empty)"
        out.append({
            "key": "passwords",
            "stat": f"{share}%",
            "text": f"Just 10 passwords make up {share}% of all guesses. The favourite is "
                    f"\u201c{best}\u201d.",
        })  # fmt: skip

    orgs = store.query(
        f"SELECT org, COUNT(*) AS c FROM attempts {where} AND org IS NOT NULL GROUP BY org", args
    )
    located = sum(r["c"] for r in orgs)
    if located >= MIN_ATTEMPTS:
        cloud = _pct(sum(r["c"] for r in orgs if CLOUD.search(r["org"])), located)
        if cloud >= 10:
            out.append({
                "key": "cloud",
                "stat": f"{cloud}%",
                "text": f"{cloud}% come from rented servers at hosting and cloud companies, "
                        "not from people's homes.",
            })  # fmt: skip

    top_c = store.query(
        f"SELECT country_name AS name, COUNT(*) AS c FROM attempts {where}"
        " AND country_name IS NOT NULL GROUP BY country_name ORDER BY c DESC LIMIT 1",
        args,
    )
    if top_c and w["countries"] > 1:
        out.append({
            "key": "country",
            "stat": f"{_pct(top_c[0]['c'], n)}%",
            "text": f"{top_c[0]['name']} sends the most, {_pct(top_c[0]['c'], n)}% of attempts, "
                    f"out of {w['countries']} countries in total.",
        })  # fmt: skip

    once = store.query(
        f"SELECT COUNT(*) AS c FROM (SELECT ip FROM attempts {where}"
        " GROUP BY ip HAVING COUNT(*) = 1)",
        args,
    )[0]["c"]
    if w["ips"] >= 10:
        heavy = store.query(
            f"SELECT COUNT(*) AS c FROM attempts {where} AND ip IN (SELECT ip FROM attempts"
            f" {where} GROUP BY ip ORDER BY COUNT(*) DESC LIMIT ?)",
            (*args, *args, max(1, w["ips"] // 10)),
        )[0]["c"]
        heavy_pct, once_pct = _pct(heavy, n), _pct(once, w["ips"])
        if heavy_pct >= 30:
            tail = f", while {once_pct}% of addresses try once and move on" if once_pct else ""
            out.append({
                "key": "persistence",
                "stat": f"{heavy_pct}%",
                "text": f"The busiest tenth of attackers make {heavy_pct}% of attempts{tail}.",
            })  # fmt: skip

    clients = store.query(
        f"SELECT client, COUNT(*) AS c FROM attempts {where} AND client IS NOT NULL"
        " GROUP BY client ORDER BY c DESC LIMIT 1",
        args,
    )
    if clients:
        c = clients[0]["client"]
        built = (
            "written in Go" if "Go" in c else "written in Python" if "paramiko" in c.lower()
            else "built on the libssh library" if "libssh" in c.lower() else None
        )  # fmt: skip
        if built:
            out.append({
                "key": "tooling",
                "stat": c.removeprefix("SSH-2.0-"),
                "text": f"The most common attack tool identifies as {c}: "
                        f"a scanning program {built}, not a person typing.",
            })  # fmt: skip
    return out


def report(store: Store, days: int = 7, now: float | None = None) -> dict[str, Any]:
    now = time.time() if now is None else now
    start, prev_start = now - days * 86400, now - 2 * days * 86400
    cur, prev = _window(store, start, now), _window(store, prev_start, start)
    args = (start, now)
    where = f"WHERE {BOTS} AND ts >= ? AND ts < ?"

    def top(col: str, limit: int = 10, label: str = "") -> list[dict[str, Any]]:
        extra = f", MAX({label}) AS label" if label else ""
        return store.query(
            f"SELECT {col} AS value, COUNT(*) AS count{extra} FROM attempts {where}"
            f" AND {col} IS NOT NULL GROUP BY {col} ORDER BY count DESC LIMIT ?",
            (*args, limit),
        )

    days_rows = store.query(
        "SELECT date(ts, 'unixepoch') AS day, COUNT(*) AS count"
        f" FROM attempts {where} GROUP BY day ORDER BY day",
        args,
    )
    attacker = store.query(
        "SELECT ip, COUNT(*) AS count, MAX(country_name) AS country, MAX(country) AS cc,"
        f" MAX(org) AS org FROM attempts {where} GROUP BY ip ORDER BY count DESC LIMIT 1",
        args,
    )
    return {
        "days": days,
        "start": start,
        "end": now,
        "current": {k: cur[k] for k in ("n", "ips", "countries")},
        "previous": {k: prev[k] for k in ("n", "ips", "countries")},
        "by_day": days_rows,
        "passwords": top("password"),
        "usernames": top("username"),
        "countries": top("country", label="country_name"),
        "orgs": top("org"),
        "top_attacker": attacker[0] if attacker else None,
        "insights": build(store, days, now),
    }
