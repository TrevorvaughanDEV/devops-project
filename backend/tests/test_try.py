from types import SimpleNamespace

from app.main import visitor_ip
from app.ratelimit import RateLimiter


def test_website_attempt_goes_through_the_honeypot(live_client):
    r = live_client.post("/api/try", json={"username": "trevor", "password": "letmein"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["result"] == "denied"
    a = body["attempt"]
    assert a["username"] == "trevor" and a["password"] == "letmein"
    assert a["method"] == "web"
    assert a["client"] == "SSH-2.0-trevorvaughan.dev_website"
    # Credited to the visitor, not to the server itself
    assert a["ip"] != "127.0.0.1"


def test_website_attempts_show_in_log_but_not_in_bot_stats(live_client):
    live_client.post("/api/try", json={"username": "visitor", "password": "pw"})
    assert live_client.get("/api/recent").json()[0]["username"] == "visitor"
    assert live_client.get("/api/summary").json()["attempts"] == 0
    assert live_client.get("/api/top/usernames").json() == []
    assert live_client.get("/api/heatmap").json() == []


def test_website_attempts_are_rate_limited(live_client):
    codes = [
        live_client.post("/api/try", json={"username": "a", "password": "b"}).status_code
        for _ in range(6)
    ]
    assert codes[:5] == [200] * 5
    assert codes[5] == 429


def test_try_validates_input(live_client):
    assert live_client.post("/api/try", json={"username": "", "password": "x"}).status_code == 422
    assert (
        live_client.post("/api/try", json={"username": "u" * 33, "password": "x"}).status_code
        == 422
    )


def test_try_without_sensor_is_unavailable(client):
    r = client.post("/api/try", json={"username": "a", "password": "b"})
    assert r.status_code == 503


def _req(peer, real_ip=None):
    headers = {"x-real-ip": real_ip} if real_ip else {}
    return SimpleNamespace(client=SimpleNamespace(host=peer), headers=headers)


def test_visitor_ip_trusts_header_only_from_proxy():
    assert visitor_ip(_req("172.17.0.1", "8.8.8.8")) == "8.8.8.8"  # Nginx via Docker
    assert visitor_ip(_req("127.0.0.1", "8.8.8.8")) == "8.8.8.8"
    assert visitor_ip(_req("9.9.9.9", "8.8.8.8")) == "9.9.9.9"  # spoofed header ignored
    assert visitor_ip(_req("172.17.0.1", "not-an-ip")) == "172.17.0.1"


def test_rate_limiter_windows():
    rl = RateLimiter([(2, 60), (3, 3600)], (100, 60))
    assert rl.check("a", now=0) == 0
    assert rl.check("a", now=1) == 0
    assert rl.check("a", now=2) > 0  # 2 per minute
    assert rl.check("b", now=2) == 0  # other visitors unaffected
    assert rl.check("a", now=61) == 0
    assert rl.check("a", now=125) > 0  # 3 per hour
    assert rl.check("a", now=3601) == 0


def test_rate_limiter_global_cap():
    rl = RateLimiter([(10, 60)], (2, 60))
    assert rl.check("a", now=0) == 0
    assert rl.check("b", now=0) == 0
    assert rl.check("c", now=0) > 0


def test_weak_password_from_the_website_is_still_refused(live_client):
    r = live_client.post("/api/try", json={"username": "root", "password": "123456"}).json()
    assert r["result"] == "denied" and r["shell"] is True
    assert r["attempt"]["accepted"] == 0
    other = live_client.post("/api/try", json={"username": "root", "password": "x7!kQ"}).json()
    assert other["shell"] is False
