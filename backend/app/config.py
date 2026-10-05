"""Settings, read once from the environment."""

import os
from dataclasses import dataclass, field
from pathlib import Path


def _bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("DATA_DIR", "data")))
    database_path: Path = field(
        default_factory=lambda: Path(os.environ.get("DATABASE_PATH", "data/attacks.db"))
    )

    # Honeypot sensor
    sensor_enabled: bool = field(default_factory=lambda: _bool("SENSOR_ENABLED", True))
    sensor_port: int = field(default_factory=lambda: int(os.environ.get("SENSOR_PORT", "2222")))
    # The port attackers actually hit (Docker may map 22 or 2222 on the host to sensor_port)
    public_port: int = field(
        default_factory=lambda: int(os.environ.get("PUBLIC_SENSOR_PORT", "2222"))
    )
    sensor_banner: str = field(
        default_factory=lambda: os.environ.get("SENSOR_BANNER", "OpenSSH_9.6p1 Ubuntu-3ubuntu13.5")
    )
    max_connections: int = field(
        default_factory=lambda: int(os.environ.get("SENSOR_MAX_CONNECTIONS", "200"))
    )
    max_connections_per_ip: int = field(
        default_factory=lambda: int(os.environ.get("SENSOR_MAX_PER_IP", "8"))
    )

    # Where the sensor lives, for drawing arcs on the map
    server_label: str = field(
        default_factory=lambda: os.environ.get("SERVER_LABEL", "Madrid, Spain")
    )
    server_lat: float = field(default_factory=lambda: float(os.environ.get("SERVER_LAT", "40.42")))
    server_lon: float = field(default_factory=lambda: float(os.environ.get("SERVER_LON", "-3.70")))

    # Enrichment (both optional)
    geo_city_db: Path = field(
        default_factory=lambda: Path(os.environ.get("GEO_CITY_DB", "/app/geo/city.mmdb"))
    )
    geo_asn_db: Path = field(
        default_factory=lambda: Path(os.environ.get("GEO_ASN_DB", "/app/geo/asn.mmdb"))
    )
    abuseipdb_key: str = field(default_factory=lambda: os.environ.get("ABUSEIPDB_KEY", ""))

    retention_days: int = field(default_factory=lambda: int(os.environ.get("RETENTION_DAYS", "90")))
    static_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("STATIC_DIR", "/app/static"))
    )


def load() -> Settings:
    return Settings()
