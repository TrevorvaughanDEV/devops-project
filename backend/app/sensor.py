"""SSH honeypot.

It speaks real SSH and records the username and password of every login attempt.
Almost all are rejected. A few of the most common weak passwords are "accepted" into
an imitation shell (see shell.py) that records every command the bot sends: nothing
is ever executed, no file is written and nothing is downloaded. Port forwarding,
SFTP, SCP and agent forwarding are all refused, and the attempt is logged.
"""

import asyncio
import ipaddress
import logging
import secrets
import socket
import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

import asyncssh

from .shell import FakeShell, urls_in

logger = logging.getLogger(__name__)
logging.getLogger("asyncssh").setLevel(logging.WARNING)

MAX_USERNAME = 64
MAX_PASSWORD = 128
MAX_CLIENT = 100
MAX_COMMAND = 1000

# Passwords that "work". Bots that get in with one of these land in the fake shell.
WEAK_PASSWORDS = frozenset({
    "123456", "password", "admin", "root", "12345678", "1234", "12345", "123456789",
    "qwerty", "1qaz2wsx", "admin123", "P@ssw0rd", "changeme", "ubuntu", "test",
    "raspberry", "111111", "abc123", "pass", "123",
})  # fmt: skip
SHELL_IDLE = 60  # seconds without input before the fake shell hangs up
SHELL_MAX = 300  # longest a shell session may last
SHELL_MAX_COMMANDS = 150  # per connection, across all its channels
SHELL_MAX_CHANNELS = 3  # session channels one connection may open
SHELL_PER_IP_DAY = 20  # accepted logins per address per day; after that, refused


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
ShellRecorder = Callable[[str, dict[str, Any]], None]


class Sensor:
    """Owns the listening server and the per-IP connection limits."""

    def __init__(
        self,
        record: Recorder,
        max_connections: int = 200,
        max_per_ip: int = 8,
        record_shell: ShellRecorder | None = None,
        shell_passwords: frozenset[str] | None = WEAK_PASSWORDS,
    ):
        self.record = record
        # Fake shell: off unless a recorder for its sessions is given
        self.record_shell = record_shell
        self.shell_passwords = shell_passwords or frozenset()
        self._shell_quota: dict[str, int] = {}
        self._quota_day = 0
        self.max_connections = max_connections
        self.max_per_ip = max_per_ip
        self.active: Counter[str] = Counter()
        # Website "try to break in" logins, keyed by the local port they connect from,
        # so the sensor can credit them to the visitor instead of to 127.0.0.1.
        self.pending: dict[int, dict[str, Any]] = {}
        self._server: asyncssh.SSHAcceptor | None = None

    def admit(self, ip: str) -> bool:
        if sum(self.active.values()) >= self.max_connections or self.active[ip] >= self.max_per_ip:
            return False
        self.active[ip] += 1
        return True

    def shell_allowed(self, ip: str) -> bool:
        """Count an accepted login against the address's daily allowance."""
        day = int(time.time() // 86400)
        if day != self._quota_day:
            self._quota_day, self._shell_quota = day, {}
        if self._shell_quota.get(ip, 0) >= SHELL_PER_IP_DAY:
            return False
        self._shell_quota[ip] = self._shell_quota.get(ip, 0) + 1
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
            encoding="utf-8",
            errors="replace",
            # Small flow-control window: no client can park megabytes in our buffers
            window=64 * 1024,
            max_pktsize=16 * 1024,
            # Logged-in connections have no login timeout, so detect dead peers
            keepalive_interval=30,
            keepalive_count_max=3,
        )
        logger.info("Honeypot listening on port %s", port)

    @property
    def port(self) -> int | None:
        """The IPv4 listening port. On a dual-stack host the server opens an IPv4 and an
        IPv6 socket, and with port 0 each gets a different port, so pick the IPv4 one:
        that's the one web_attempt() connects to on 127.0.0.1."""
        if not self._server:
            return None
        sockets = self._server.sockets
        ipv4 = [s for s in sockets if s.family == socket.AF_INET]
        return (ipv4 or sockets)[0].getsockname()[1]

    async def web_attempt(
        self, visitor_ip: str, username: str, password: str, timeout: float = 10
    ) -> dict[str, Any] | None:
        """Make a real SSH login against this honeypot on a website visitor's behalf.

        The guess goes through exactly the same handshake and recorder as an attack;
        only the source address is swapped for the visitor's. Returns the recorded event.
        """
        if self.port is None:
            raise RuntimeError("Honeypot is not running")
        loop = asyncio.get_running_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setblocking(False)
        sock.bind(("127.0.0.1", 0))
        local_port = sock.getsockname()[1]
        entry: dict[str, Any] = {"ip": visitor_ip, "event": None}
        self.pending[local_port] = entry
        try:
            await asyncio.wait_for(loop.sock_connect(sock, ("127.0.0.1", self.port)), timeout)
            try:
                conn = await asyncio.wait_for(
                    asyncssh.connect(
                        sock=sock,
                        username=username,
                        password=password,
                        known_hosts=None,
                        client_keys=None,
                        agent_path=None,
                        preferred_auth="password",
                        client_version="trevorvaughan.dev_website",
                    ),
                    timeout,
                )
                conn.close()  # never reached: the honeypot rejects every login
            except asyncssh.PermissionDenied:
                pass
        finally:
            self.pending.pop(local_port, None)
            sock.close()
        return entry["event"]

    async def _run_shell(self, process: asyncssh.SSHServerProcess) -> None:
        """One session channel on an "accepted" login: an exec command or an
        interactive shell. Everything is answered by FakeShell; nothing runs."""
        server: _HoneypotServer | None = process.get_extra_info("honeypot")
        if server is None or self.record_shell is None or process.subsystem:
            process.exit(1)
            return
        shell = FakeShell(server.username)
        server.open_session()
        try:
            if process.command is not None:
                # Cap first: everything after this (regexes, the fake shell) sees at most
                # MAX_COMMAND characters, so no input can make it slow or memory-hungry.
                command = process.command[:MAX_COMMAND]
                if server.log_command(command):
                    process.stdout.write(shell.run(command))
                    await process.stdout.drain()
            else:
                await asyncio.wait_for(self._interactive(process, server, shell), SHELL_MAX)
        except (TimeoutError, asyncssh.BreakReceived, asyncssh.TerminalSizeChanged):
            pass
        except (asyncssh.Error, OSError, ConnectionError):
            pass
        finally:
            server.close_session()
            try:
                process.exit(0)
            except (OSError, asyncssh.Error):
                pass

    async def _interactive(self, process, server: "_HoneypotServer", shell: FakeShell) -> None:
        # With a terminal, AsyncSSH's line editor echoes input and turns \n into \r\n.
        process.stdout.write(shell.motd() + "\n" + shell.prompt)
        while True:
            try:
                line = await asyncio.wait_for(process.stdin.readline(), SHELL_IDLE)
            except (asyncssh.TerminalSizeChanged, asyncssh.SignalReceived):
                continue  # window resized, or Ctrl-C: carry on like a real shell
            if not line:
                return  # client closed the channel
            line = line.rstrip("\r\n")[:MAX_COMMAND]
            if line.strip():
                if not server.log_command(line):
                    return  # out of commands for this connection
                out = shell.run(line)
                if out:
                    process.stdout.write(out)
            if shell.done:
                process.stdout.write("logout\n")
                return
            process.stdout.write(shell.prompt)
            await process.stdout.drain()  # a client that never reads just stalls itself

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
        self.web: dict[str, Any] | None = None
        self.username = "root"
        self.password: str | None = None
        self.session: str | None = None
        self.opened = False
        self.commands = 0
        self.channels = 0

    def connection_made(self, conn: asyncssh.SSHServerConnection) -> None:
        peer = conn.get_extra_info("peername") or ("unknown", 0)
        self.ip = _normalise_ip(str(peer[0]))
        # Only a connection from inside this process (loopback, registered port) can
        # claim to be a website visitor; outside attackers can't reach loopback.
        if self.ip == "127.0.0.1" and peer[1] in self.sensor.pending:
            self.web = self.sensor.pending[peer[1]]
            self.ip = self.web["ip"]
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

    def _record(
        self, username: str, password: str | None, method: str, accepted: bool = False
    ) -> None:
        event = {
            "ts": time.time(),
            "ip": self.ip,
            "username": _clean(username, MAX_USERNAME) or "",
            "password": _clean(password, MAX_PASSWORD),
            "method": "web" if self.web is not None else method,
            "client": self._client_version(),
            "accepted": 1 if accepted else 0,
        }
        try:
            self.sensor.record(event)
            if self.web is not None:
                self.web["event"] = event
        except Exception:  # never let a storage error crash the SSH handshake
            logger.exception("Failed to record attempt from %s", self.ip)

    def begin_auth(self, username: str) -> bool:
        return True  # authentication is always required

    def password_auth_supported(self) -> bool:
        return True

    def validate_password(self, username: str, password: str) -> bool:
        # Website visitors are always refused: the "try to break in" box is a demo.
        accept = (
            self.web is None
            and self.sensor.record_shell is not None
            and password in self.sensor.shell_passwords
            and self.sensor.shell_allowed(self.ip)
        )
        self._record(username, password, "password", accepted=accept)
        if accept:
            self.username = _clean(username, MAX_USERNAME) or "root"
            self.password = _clean(password, MAX_PASSWORD)
            self.session = secrets.token_hex(8)
            self.conn.set_extra_info(honeypot=self)
            # After login there is no login timeout, so put a hard limit on the visit.
            asyncio.get_running_loop().call_later(SHELL_MAX + 30, self.conn.close)
        return accept

    def session_requested(self):
        """A channel for a shell or command. Only after an accepted login, and only a
        few per connection, so one client can't open hundreds of fake shells."""
        self.channels += 1
        if self.session is None or self.channels > SHELL_MAX_CHANNELS:
            return False
        # No SFTP factory and SCP off: those requests get refused or exit 1.
        return asyncssh.SSHServerProcess(self.sensor._run_shell, None, 0, False)

    # --- after an accepted login -------------------------------------------------

    def _shell_event(self, kind: str, **data: Any) -> None:
        if self.session is None or self.sensor.record_shell is None:
            return
        try:
            self.sensor.record_shell(kind, {"session": self.session, "ts": time.time(), **data})
        except Exception:
            logger.exception("Failed to record shell %s from %s", kind, self.ip)

    def open_session(self) -> None:
        if not self.opened:
            self.opened = True
            self._shell_event(
                "open",
                ip=self.ip,
                username=self.username,
                password=self.password,
                client=self._client_version(),
            )

    def close_session(self) -> None:
        self._shell_event("close", commands=self.commands)

    def log_command(self, command: str) -> bool:
        """Record a command. False once this connection has used up its allowance."""
        if self.commands >= SHELL_MAX_COMMANDS:
            return False
        self.commands += 1
        command = command[:MAX_COMMAND]
        text = _clean(command.replace("\n", " ; "), MAX_COMMAND) or ""
        self._shell_event("command", ip=self.ip, command=text, urls=" ".join(urls_in(command)))
        return True

    def connection_requested(self, dest_host, dest_port, orig_host, orig_port):
        # Bots try to use hacked servers as proxies. Record where to, then refuse.
        if self.session:
            self.open_session()
            self.log_command(f"[tunnel to {_clean(str(dest_host), 120)}:{int(dest_port)}]")
        return False

    def server_requested(self, listen_host, listen_port):
        return False

    def public_key_auth_supported(self) -> bool:
        return True

    def validate_public_key(self, username: str, key: asyncssh.SSHKey) -> bool:
        self._record(username, None, "publickey")
        return False
