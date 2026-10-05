import time

from tests.conftest import attempt


def record(client, **kw):
    event = attempt(**kw)
    event["ts"] = event["ts"] or time.time()
    client.portal.call(client.app.state.record, event)


def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_meta_describes_sensor(client):
    meta = client.get("/api/meta").json()
    assert meta["port"] == 2222
    assert meta["server"]["label"]
    assert meta["sensor_running"] is False


def test_summary_counts_window(client):
    record(client, ip="203.0.113.1")
    record(client, ip="203.0.113.1", password="admin")
    record(client, ip="198.51.100.9", ts=time.time() - 3 * 86400)
    s = client.get("/api/summary?hours=24").json()
    assert s["attempts"] == 2
    assert s["ips"] == 1
    assert s["total_attempts"] == 3


def test_top_passwords_and_usernames(client):
    for pw in ["123456", "123456", "admin", "123456"]:
        record(client, password=pw)
    record(client, username="ubuntu", password="ubuntu")
    pws = client.get("/api/top/passwords").json()
    assert pws[0] == {"value": "123456", "count": 3, "ips": 1}
    users = client.get("/api/top/usernames").json()
    assert users[0]["value"] == "root"


def test_top_rejects_unknown_list(client):
    assert client.get("/api/top/drop%20table").status_code == 404


def test_query_limits_are_enforced(client):
    assert client.get("/api/summary?hours=0").status_code == 422
    assert client.get("/api/recent?limit=5000").status_code == 422


def test_map_only_includes_located_ips(client):
    store = client.app.state.store
    store.add_attempt(
        {
            **attempt(ip="203.0.113.5"),
            "ts": time.time(),
            "lat": 52.5,
            "lon": 13.4,
            "country": "DE",
            "city": "Berlin",
        }
    )
    record(client, ip="203.0.113.6")  # no geo database in tests, so no location
    points = client.get("/api/map").json()
    assert [p["ip"] for p in points] == ["203.0.113.5"]


def test_recent_newest_first(client):
    record(client, username="first")
    record(client, username="second")
    names = [e["username"] for e in client.get("/api/recent?limit=2").json()]
    assert names == ["second", "first"]


def test_ip_detail(client):
    record(client, ip="203.0.113.44", password="pass1")
    record(client, ip="203.0.113.44", password="pass1")
    d = client.get("/api/ip/203.0.113.44").json()
    assert d["attempts"] == 2
    assert d["credentials"][0] == {"username": "root", "password": "pass1", "count": 2}
    assert d["clients"] == ["SSH-2.0-Go"]


def test_ip_detail_errors(client):
    assert client.get("/api/ip/not-an-ip").status_code == 400
    assert client.get("/api/ip/203.0.113.250").status_code == 404


def test_heatmap_and_timeline(client):
    record(client)
    assert sum(c["count"] for c in client.get("/api/heatmap").json()) == 1
    assert sum(c["count"] for c in client.get("/api/timeline").json()) == 1


def test_live_feed_pushes_new_attempts(client):
    with client.websocket_connect("/api/live") as ws:
        record(client, username="admin", password="hunter2")
        msg = ws.receive_json()
    assert msg["type"] == "attempt"
    assert msg["data"]["username"] == "admin"
    assert msg["data"]["password"] == "hunter2"
    assert "asn" not in msg["data"]


def test_frontend_served_with_spa_fallback(client):
    assert "Who's Knocking" in client.get("/").text
    assert "Who's Knocking" in client.get("/ip/1.2.3.4").text
    assert client.get("/api/nope").status_code == 404


def test_static_path_traversal_blocked(client):
    r = client.get("/..%2F..%2Fattacks.db")
    assert "Who's Knocking" in r.text


def test_prune_removes_old_attempts(client):
    record(client, ts=time.time() - 100 * 86400)
    record(client)
    assert client.app.state.store.prune(90) == 1


def test_backfill_locations(client):
    store = client.app.state.store
    record(client, ip="203.0.113.70")
    assert store.unlocated_ips() == ["203.0.113.70"]
    geo = {"country": "IE", "country_name": "Ireland", "city": "Dublin", "lat": 53.3, "lon": -6.3}
    assert store.set_location("203.0.113.70", geo) == 1
    assert store.unlocated_ips() == []
    assert client.get("/api/map").json()[0]["city"] == "Dublin"


def test_broken_geo_database_does_not_stop_the_app(tmp_path):
    from app.geo import GeoLookup

    bad = tmp_path / "city.mmdb"
    bad.write_bytes(b"")
    geo = GeoLookup(bad, tmp_path / "none.mmdb")
    assert not geo.enabled
    assert geo.lookup("8.8.8.8") == {}
