"""Fill a local database with realistic-looking attempts, for UI development only.

    DATABASE_PATH=data/demo.db python scripts/demo_data.py

Never run this against the production database: everything it writes is invented.
The addresses come from the documentation ranges (RFC 5737), so none are real hosts.
"""

import os
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import Store  # noqa: E402

PLACES = [
    ("CN", "China", "Shanghai", 31.23, 121.47, "China Telecom", 30),
    ("CN", "China", "Beijing", 39.9, 116.4, "China Unicom", 18),
    ("US", "United States", "Ashburn", 39.04, -77.49, "Amazon.com, Inc.", 16),
    ("US", "United States", "Santa Clara", 37.35, -121.95, "DigitalOcean, LLC", 10),
    ("NL", "Netherlands", "Amsterdam", 52.37, 4.9, "DigitalOcean, LLC", 9),
    ("DE", "Germany", "Frankfurt", 50.11, 8.68, "Hetzner Online GmbH", 9),
    ("RU", "Russia", "Moscow", 55.75, 37.62, "Rostelecom", 8),
    ("IN", "India", "Mumbai", 19.08, 72.88, "Bharti Airtel", 7),
    ("BR", "Brazil", "São Paulo", -23.55, -46.63, "Claro S.A.", 6),
    ("VN", "Vietnam", "Hanoi", 21.03, 105.85, "VNPT Corp", 6),
    ("KR", "South Korea", "Seoul", 37.57, 126.98, "Korea Telecom", 5),
    ("SG", "Singapore", "Singapore", 1.35, 103.82, "Tencent Cloud", 5),
    ("FR", "France", "Paris", 48.86, 2.35, "OVH SAS", 4),
    ("ID", "Indonesia", "Jakarta", -6.2, 106.85, "PT Telkom Indonesia", 4),
    ("GB", "United Kingdom", "London", 51.51, -0.13, "Linode", 3),
    ("ZA", "South Africa", "Johannesburg", -26.2, 28.05, "Afrihost", 2),
    ("AR", "Argentina", "Buenos Aires", -34.6, -58.38, "Telecom Argentina", 2),
    ("AU", "Australia", "Sydney", -33.87, 151.21, "Vultr Holdings", 2),
]
USERS = (
    ["root"] * 30
    + ["admin"] * 8
    + [
        "ubuntu",
        "test",
        "user",
        "oracle",
        "postgres",
        "git",
        "pi",
        "ftpuser",
        "deploy",
        "support",
        "guest",
        "hadoop",
        "debian",
    ]
    * 2
)
PASSWORDS = (
    ["123456"] * 12
    + ["password"] * 6
    + ["admin"] * 6
    + ["root"] * 5
    + [
        "12345678",
        "123",
        "1234",
        "qwerty",
        "P@ssw0rd",
        "admin123",
        "toor",
        "111111",
        "raspberry",
        "ubuntu",
        "test",
        "1qaz2wsx",
        "abc123",
        "",
        "changeme",
        "Huawei@123",
    ]
    * 2
)
CLIENTS = (
    ["SSH-2.0-Go"] * 6
    + ["SSH-2.0-libssh2_1.10.0"] * 3
    + ["SSH-2.0-OpenSSH_8.9p1", "SSH-2.0-PuTTY_Release_0.78", "SSH-2.0-paramiko_3.4.0"]
)


def main(n: int = 2600) -> None:
    store = Store(os.environ.get("DATABASE_PATH", "data/demo.db"))
    weights = [p[-1] for p in PLACES]
    now = time.time()
    hosts = []
    for i in range(140):
        place = random.choices(PLACES, weights)[0]
        net = random.choice(["192.0.2", "198.51.100", "203.0.113"])
        jitter = (random.uniform(-1.5, 1.5), random.uniform(-1.5, 1.5))
        hosts.append((f"{net}.{i + 1}", place, jitter, random.choice(CLIENTS)))
    for _ in range(n):
        ip, (cc, cn, city, lat, lon, org, _w), (dy, dx), client = random.choice(hosts)
        age = (
            random.expovariate(1 / (3 * 86400))
            if random.random() < 0.6
            else random.uniform(0, 86400)
        )
        store.add_attempt(
            {
                "ts": now - age,
                "ip": ip,
                "username": random.choice(USERS),
                "password": random.choice(PASSWORDS),
                "method": "password",
                "client": client,
                "country": cc,
                "country_name": cn,
                "city": city,
                "lat": lat + dy,
                "lon": lon + dx,
                "asn": 4134,
                "org": org,
            }
        )
    print(f"Wrote {n} demo attempts")


if __name__ == "__main__":
    main()
