import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings(tmp_path):
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html><title>Who's Knocking</title>")
    return Settings(
        data_dir=tmp_path,
        database_path=tmp_path / "attacks.db",
        static_dir=static,
        geo_city_db=tmp_path / "missing-city.mmdb",
        geo_asn_db=tmp_path / "missing-asn.mmdb",
        abuseipdb_key="",
    )


@pytest.fixture
def client(settings):
    app = create_app(settings, start_sensor=False)
    with TestClient(app) as c:
        yield c


def attempt(ip="203.0.113.7", username="root", password="123456", **extra):
    event = {
        "ip": ip,
        "username": username,
        "password": password,
        "method": "password",
        "client": "SSH-2.0-Go",
        "ts": extra.pop("ts", None),
    }
    event.update(extra)
    return event


@pytest.fixture
def live_client(settings):
    """App with the honeypot actually listening (on a random free port)."""
    from dataclasses import replace

    app = create_app(replace(settings, sensor_port=0), start_sensor=True)
    with TestClient(app) as c:
        yield c
