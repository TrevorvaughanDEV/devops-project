"""IP to location and network owner, using the free DB-IP Lite databases.

Both files are optional: without them the honeypot still records everything,
the map just has fewer points.
"""

import ipaddress
import logging
from pathlib import Path
from typing import Any

import maxminddb

logger = logging.getLogger(__name__)


class GeoLookup:
    def __init__(self, city_db: Path, asn_db: Path):
        self._city = self._open(city_db)
        self._asn = self._open(asn_db)

    @staticmethod
    def _open(path: Path):
        if path.is_file():
            try:
                db = maxminddb.open_database(str(path))
            except (OSError, ValueError, maxminddb.InvalidDatabaseError) as exc:
                logger.error("Geo database %s is unreadable: %s", path, exc)
                return None
            logger.info("Loaded geo database %s", path)
            return db
        logger.warning("Geo database %s not found; lookups disabled", path)
        return None

    @property
    def enabled(self) -> bool:
        return self._city is not None

    def lookup(self, ip: str) -> dict[str, Any]:
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return {}
        if not addr.is_global:
            return {}
        out: dict[str, Any] = {}
        if self._city:
            rec = self._city.get(ip) or {}
            country = rec.get("country") or {}
            loc = rec.get("location") or {}
            out.update(
                country=country.get("iso_code"),
                country_name=(country.get("names") or {}).get("en"),
                city=((rec.get("city") or {}).get("names") or {}).get("en"),
                lat=loc.get("latitude"),
                lon=loc.get("longitude"),
            )
        if self._asn:
            rec = self._asn.get(ip) or {}
            out.update(
                asn=rec.get("autonomous_system_number"),
                org=rec.get("autonomous_system_organization"),
            )
        return out
