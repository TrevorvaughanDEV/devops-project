"""Low-interaction SSH honeypot.

It speaks real SSH, records the username and password of every login attempt,
and always rejects them. No attacker ever gets a shell, so there is nothing on
this side for them to break into: the only thing exposed is the SSH handshake,
handled by the AsyncSSH library.
"""

import ipaddress
import logging
import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

import asyncssh

logger = logging.getLogger(__name__)
logging.getLogger("asyncssh").setLevel(logging.WARNING)

MAX_USERNAME = 64
MAX_PASSWORD = 128
MAX_CLIENT = 100


def _clean(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    # Keep what attackers typed, minus control characters that would garble logs.
    text = "".join(ch for ch in value if ch.isprintable() or ch == " ")
    return text[:limit]


def _normalise_ip(raw: str) -> str:
    try:
        addr = ipaddress.ip_address(raw.split("%")[0])
    except ValueError:
        return raw
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        return str(addr.ipv4_mapped)
    return str(addr)


def load_host_keys(data_dir: Path) -> list[asyncssh.SSHKey]:
    """Load the sensor's host keys, generating them on first run.

    Keeping them on the data volume means the server's fingerprint stays the same
    across deploys, like a real server's would.
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    keys = []
    for alg, name in (("ssh-ed25519", "ed25519"), ("ssh-rsa", "rsa")):
        path = data_dir / f"ssh_host_{name}_key"
        if not path.exists():
            key = (
                asyncssh.generate_private_key(alg, key_size=2048)
                if name == "rsa"
                else (asyncssh.generate_private_key(alg))
            )
            key.write_private_key(str(path))
            path.chmod(0o600)
            logger.info("Generated %s host key", name)
        keys.append(asyncssh.read_private_key(str(path)))
    return keys


Recorder = Callable[[dict[str, Any]], None]


class Sensor:
    """Owns the listening server and the per-IP connection limits."""

    def __init__(
        self,
        record: Recorder,
        max_connections: int = 200,
        max_per_ip: int = 8,
    ):
        self.record = record
        self.max_connections = max_connections
        self.max_per_ip = max_per_ip
        self.active: Counter[str] = Counter()
        self._server: asyncssh.SSHAcceptor | None = None

    def admit(self, ip: str) -> bool:
        if sum(self.active.values()) >= self.max_connections or self.active[ip] >= self.max_per_ip:
            return False
        self.active[ip] += 1
        return True

    def release(self, ip: str) -> None:
        self.active[ip] -= 1
        if self.active[ip] <= 0:
            del self.active[ip]

    async def start(self, port: int, host_keys: list, banner: str, host: str = "") -> None:
        self._server = await asyncssh.create_server(
            lambda: _HoneypotServer(self),
            host,
            port,
            server_host_keys=host_keys,
            server_version=banner,
            login_timeout=30,
            allow_scp=False,
            agent_forwarding=False,
            x11_forwarding=False,
        )
        logger.info("Honeypot listening on port %s", port)

    @property
    def port(self) -> int | None:
        if not self._server:
            return None
        return self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()


class _HoneypotServer(asyncssh.SSHServer):
    def __init__(self, sensor: Sensor):
        self.sensor = sensor
        self.ip = "unknown"
        self.client: str | None = None
        self.admitted = False

    def connection_made(self, conn: asyncssh.SSHServerConnection) -> None:
        peer = conn.get_extra_info("peername") or ("unknown", 0)
        self.ip = _normalise_ip(str(peer[0]))
        self.admitted = self.sensor.admit(self.ip)
        if not self.admitted:
            conn.abort()
            return
        self.conn = conn

    def connection_lost(self, exc: Exception | None) -> None:
        if self.admitted:
            self.sensor.release(self.ip)

    def _client_version(self) -> str | None:
        if self.client is None and hasattr(self, "conn"):
            raw = self.conn.get_extra_info("client_version")
            self.client = _clean(raw.decode() if isinstance(raw, bytes) else raw, MAX_CLIENT)
        return self.client

    def _record(self, username: str, password: str | None, method: str) -> None:
        try:
            self.sensor.record(
                {
                    "ts": time.time(),
                    "ip": self.ip,
                    "username": _clean(username, MAX_USERNAME) or "",
                    "password": _clean(password, MAX_PASSWORD),
                    "method": method,
                    "client": self._client_version(),
                }
            )
        except Exception:  # never let a storage error crash the SSH handshake
            logger.exception("Failed to record attempt from %s", self.ip)

    def begin_auth(self, username: str) -> bool:
        return True  # authentication is always required

    def password_auth_supported(self) -> bool:
        return True

    def validate_password(self, username: str, password: str) -> bool:
        self._record(username, password, "password")
        return False

    def public_key_auth_supported(self) -> bool:
        return True

    def validate_public_key(self, username: str, key: asyncssh.SSHKey) -> bool:
        self._record(username, None, "publickey")
        return False
