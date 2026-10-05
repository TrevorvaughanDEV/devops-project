import asyncio

import asyncssh
import pytest

from app.sensor import Sensor, _clean, _normalise_ip, load_host_keys


@pytest.fixture
async def sensor(tmp_path):
    events = []
    s = Sensor(events.append, max_connections=10, max_per_ip=2)
    await s.start(0, load_host_keys(tmp_path), "OpenSSH_9.6p1 Ubuntu-3ubuntu13.5", host="127.0.0.1")
    s.events = events
    yield s
    await s.stop()


async def try_login(port, username, password):
    with pytest.raises(asyncssh.PermissionDenied):
        async with asyncssh.connect(
            "127.0.0.1",
            port,
            username=username,
            password=password,
            known_hosts=None,
            client_keys=None,
            agent_path=None,
        ):
            pass


async def test_records_password_and_rejects(sensor):
    await try_login(sensor.port, "root", "toor")
    pw = [e for e in sensor.events if e["method"] == "password"]
    assert pw and pw[0]["username"] == "root" and pw[0]["password"] == "toor"
    assert pw[0]["ip"] == "127.0.0.1"
    assert pw[0]["client"].startswith("SSH-2.0-AsyncSSH")


async def test_banner_looks_like_openssh(sensor):
    reader, writer = await asyncio.open_connection("127.0.0.1", sensor.port)
    banner = await reader.readline()
    writer.close()
    assert banner.startswith(b"SSH-2.0-OpenSSH_9.6p1")


async def test_host_keys_persist(tmp_path):
    first = [k.get_fingerprint() for k in load_host_keys(tmp_path)]
    second = [k.get_fingerprint() for k in load_host_keys(tmp_path)]
    assert first == second and len(first) == 2


def test_per_ip_limit():
    s = Sensor(lambda e: None, max_connections=3, max_per_ip=2)
    assert s.admit("1.1.1.1") and s.admit("1.1.1.1")
    assert not s.admit("1.1.1.1")
    assert s.admit("2.2.2.2")
    assert not s.admit("3.3.3.3")  # global cap
    s.release("1.1.1.1")
    assert s.admit("3.3.3.3")


def test_input_cleaning():
    assert _clean("ab\x00c\x1b[31m", 10) == "abc[31m"
    assert _clean("x" * 500, 128) == "x" * 128
    assert _clean(None, 5) is None
    assert _normalise_ip("::ffff:203.0.113.9") == "203.0.113.9"


async def test_port_is_the_ipv4_listener_on_dual_stack(tmp_path):
    # Listening on all interfaces opens IPv4 and (where available) IPv6 sockets;
    # with port 0 they can get different ports. .port must be the IPv4 one.
    import socket

    s = Sensor(lambda e: None)
    await s.start(0, load_host_keys(tmp_path), "OpenSSH_9.6p1", host="")
    try:
        ipv4 = [x for x in s._server.sockets if x.family == socket.AF_INET]
        assert s.port == ipv4[0].getsockname()[1]
        reader, writer = await asyncio.open_connection("127.0.0.1", s.port)
        assert (await reader.readline()).startswith(b"SSH-2.0-")
        writer.close()
    finally:
        await s.stop()
