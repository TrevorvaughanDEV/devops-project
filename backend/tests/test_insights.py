import time

from app import insights, og
from tests.conftest import attempt

NOW = time.time()


def seed(store, rows):
    for i, (user, pw, cc, org, client) in enumerate(rows):
        store.add_attempt({
            **attempt(ip=f"203.0.113.{i % 40}", username=user, password=pw, client=client),
            "ts": NOW - 3600 - i, "country": cc,
            "country_name": {"CN": "China", "US": "United States"}[cc],
            "org": org, "lat": 31.2, "lon": 121.4,
        })  # fmt: skip


def test_no_insights_without_enough_data(client):
    seed(client.app.state.store, [("root", "123456", "CN", "China Telecom", "SSH-2.0-Go")] * 5)
    assert client.get("/api/insights").json() == []


def test_insights_describe_the_data(client):
    rows = [("root", "123456", "CN", "Tencent Cloud", "SSH-2.0-Go")] * 30 + [
        ("admin", "admin", "US", "DigitalOcean, LLC", "SSH-2.0-Go")
    ] * 10
    seed(client.app.state.store, rows)
    found = {i["key"]: i for i in client.get("/api/insights").json()}
    assert found["root"]["stat"] == "75%"
    assert "123456" in found["passwords"]["text"]
    assert found["cloud"]["stat"] == "100%"
    assert found["country"]["text"].startswith("China sends the most, 75%")
    assert "Go" in found["tooling"]["text"]
    assert "rate" in found
    assert "persistence" not in found  # evenly spread attackers: nothing to say


def test_visitors_are_not_in_insights(client):
    store = client.app.state.store
    for _ in range(30):
        store.add_attempt({**attempt(), "ts": NOW - 60, "method": "web"})
    assert client.get("/api/insights").json() == []


def test_weekly_report_compares_weeks(client):
    store = client.app.state.store
    seed(store, [("root", "123456", "CN", "China Telecom", "SSH-2.0-Go")] * 25)
    store.add_attempt({**attempt(ip="198.51.100.1"), "ts": NOW - 9 * 86400})
    r = client.get("/api/report?days=7").json()
    assert r["current"]["n"] == 25 and r["previous"]["n"] == 1
    assert r["passwords"][0] == {"value": "123456", "count": 25}
    assert r["countries"][0]["label"] == "China"
    assert r["top_attacker"]["count"] >= 1
    assert sum(d["count"] for d in r["by_day"]) == 25


def test_report_ok_when_empty(client):
    r = client.get("/api/report").json()
    assert r["current"]["n"] == 0 and r["insights"] == [] and r["top_attacker"] is None


def test_preview_image(client):
    seed(client.app.state.store, [("root", "123456", "CN", "China Telecom", "SSH-2.0-Go")] * 3)
    r = client.get("/og.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_projection_matches_d3():
    # Values printed by d3.geoNaturalEarth1() with the same fitExtent
    assert [round(v, 2) for v in og.project(-3.7, 40.42)] == [771.48, 267.69]
    assert [round(v, 2) for v in og.project(151.2, -33.9)] == [1137.22, 483.41]


def test_rate_wording():
    assert insights._every(0.25) == "4 attempts every second"
    assert insights._every(30) == "one attempt every 30 seconds"
    assert insights._every(600) == "one attempt every 10 minutes"


def test_report_includes_shell_and_botnets(client):
    r = client.get("/api/report").json()
    assert r["shell"]["logins"] == 0 and r["campaigns"] == []
