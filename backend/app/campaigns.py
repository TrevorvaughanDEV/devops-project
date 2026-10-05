"""Find botnets: groups of machines working through the same password list.

A single address trying root/123456 tells you little. Hundreds of addresses in a dozen
countries trying the same 60 username/password pairs, with the same SSH software,
are one operation run from one list. This groups them.

How: for each attacking address, take the set of credentials it tried, minus the
generic ones that many unrelated tools try (root/123456 and friends: a credential is
generic when addresses running GENERIC_CLIENTS or more different SSH clients try it).
Those say nothing about who is behind an attack and would chain everyone together.
Within each
SSH client version, link two addresses when their sets overlap heavily (at least
MIN_SHARED pairs in common, covering at least OVERLAP of the smaller set). Overlap is
measured against the smaller set, not the union, because botnets often hand each
machine a slice of the list. Connected groups of MIN_MEMBERS or more are campaigns.

Sets are stored as integer bitmasks, so each comparison is one AND and a popcount.
Results are cached for a few minutes; the page polls far more often than the
answer changes.
"""

import hashlib
import threading
import time
from collections import Counter, defaultdict
from typing import Any

from .db import Store

MIN_CREDS = 4  # an address needs to try at least this many pairs to be compared
MIN_SHARED = 4
OVERLAP = 0.5
MIN_MEMBERS = 3
GENERIC_CLIENTS = 3
MAX_PER_GROUP = 1500
MAX_CREDS_PER_IP = 200  # a sprayer trying thousands of unique pairs gets sampled
CACHE_SECONDS = 600

_lock = threading.Lock()
_compute_lock = threading.Lock()  # one computation at a time; the rest wait for its result


class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def _cluster(masks: list[int]) -> list[list[int]]:
    sizes = [m.bit_count() for m in masks]
    uf = _UnionFind(len(masks))
    for i, mi in enumerate(masks):
        si = sizes[i]
        for j in range(i + 1, len(masks)):
            shared = (mi & masks[j]).bit_count()
            if shared >= MIN_SHARED and shared >= OVERLAP * min(si, sizes[j]):
                uf.union(i, j)
    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(len(masks)):
        groups[uf.find(i)].append(i)
    return [g for g in groups.values() if len(g) >= MIN_MEMBERS]


def _compute(store: Store, days: int, now: float) -> tuple[list[dict[str, Any]], dict[str, str]]:
    since = now - days * 86400
    args = (since, now)
    where = "method = 'password' AND ts >= ? AND ts < ?"
    ips = {
        r["ip"]: r
        for r in store.query(
            "SELECT ip, COUNT(*) AS n, MAX(client) AS client, MAX(country) AS cc,"
            " MAX(country_name) AS country, MAX(org) AS org, MIN(ts) AS first, MAX(ts) AS last"
            f" FROM attempts WHERE {where} GROUP BY ip",
            args,
        )
    }
    total = sum(r["n"] for r in ips.values())
    creds: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for r in store.query(
        f"SELECT DISTINCT ip, username, password FROM attempts WHERE {where}"
        " AND password IS NOT NULL",
        args,
    ):
        if len(creds[r["ip"]]) < MAX_CREDS_PER_IP:
            creds[r["ip"]].add((r["username"], r["password"]))

    tools: dict[tuple[str, str], set[str]] = defaultdict(set)
    for ip, cs in creds.items():
        for c in cs:
            tools[c].add(ips[ip]["client"] or "?")
    generic = {c for c, t in tools.items() if len(t) >= GENERIC_CLIENTS}
    creds = {ip: cs - generic for ip, cs in creds.items()}

    by_client: dict[str, list[str]] = defaultdict(list)
    for ip, cs in creds.items():
        if len(cs) >= MIN_CREDS:
            by_client[ips[ip]["client"] or "?"].append(ip)

    found: list[dict[str, Any]] = []
    for client, members in by_client.items():
        members = sorted(members, key=lambda ip: -ips[ip]["n"])[:MAX_PER_GROUP]
        index: dict[tuple[str, str], int] = {}
        masks = []
        for ip in members:
            m = 0
            for c in creds[ip]:
                m |= 1 << index.setdefault(c, len(index))
            masks.append(m)
        for group in _cluster(masks):
            group_ips = [members[i] for i in group]
            found.append(_describe(group_ips, ips, creds, client, total))

    found.sort(key=lambda c: -c["attempts"])
    member_of = {}
    for c in found:
        for ip in c.pop("_all"):
            member_of[ip] = c["id"]
    return found, member_of


def _describe(group_ips, ips, creds, client, total) -> dict[str, Any]:
    rows = [ips[ip] for ip in group_ips]
    coverage: Counter[tuple[str, str]] = Counter()
    for ip in group_ips:
        coverage.update(creds[ip])
    signature = [c for c, _ in coverage.most_common(6)]
    attempts = sum(r["n"] for r in rows)
    countries = Counter((r["cc"], r["country"]) for r in rows if r["cc"])
    orgs = Counter(r["org"] for r in rows if r["org"])
    key = "|".join(f"{u}\0{p}" for u, p in sorted(signature)) + f"|{client}"
    rows.sort(key=lambda r: -r["n"])
    return {
        "id": hashlib.blake2b(key.encode(), digest_size=3).hexdigest(),
        "ips": len(group_ips),
        "attempts": attempts,
        "share": round(100 * attempts / total) if total else 0,
        "client": None if client == "?" else client,
        "list_size": len(coverage),  # distinctive pairs only; generic ones are excluded
        "first_seen": min(r["first"] for r in rows),
        "last_seen": max(r["last"] for r in rows),
        "countries": [
            {"value": cc, "label": name, "count": n} for (cc, name), n in countries.most_common(8)
        ],
        "n_countries": len(countries),
        "networks": [{"value": o, "count": n} for o, n in orgs.most_common(3)],
        "signature": [
            {"username": u, "password": p, "ips": coverage[(u, p)]} for u, p in signature
        ],
        "members": [{"ip": r["ip"], "count": r["n"], "country": r["cc"]} for r in rows[:12]],
        "_all": group_ips,
    }


def _cached(store: Store, days: int) -> tuple[list[dict[str, Any]], dict[str, str]]:
    def lookup():
        with _lock:
            hit = store.__dict__.setdefault("_campaign_cache", {}).get(days)
        return hit if hit and time.time() - hit[0] < CACHE_SECONDS else None

    if hit := lookup():
        return hit[1], hit[2]
    with _compute_lock:
        if hit := lookup():  # someone else computed it while we waited
            return hit[1], hit[2]
        now = time.time()
        result, member_of = _compute(store, days, now)
        with _lock:
            store.__dict__["_campaign_cache"][days] = (now, result, member_of)
    return result, member_of


def find(store: Store, days: int = 7, limit: int = 8) -> list[dict[str, Any]]:
    return _cached(store, days)[0][:limit]


def membership(store: Store, ip: str, days: int = 7) -> dict[str, Any] | None:
    """The campaign an address belongs to, if any, in brief."""
    result, member_of = _cached(store, days)
    cid = member_of.get(ip)
    c = next((c for c in result if c["id"] == cid), None)
    if not c:
        return None
    return {k: c[k] for k in ("id", "ips", "n_countries", "list_size", "client")}
