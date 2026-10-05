"""Optional AbuseIPDB lookups, cached for a day, only when someone opens an IP."""

import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)
CACHE_SECONDS = 86400


async def enrich(store, ip: str, api_key: str) -> None:
    if not api_key:
        return
    cached = store.ip_detail(ip)
    if cached and cached.get("intel") and time.time() - cached["intel"]["fetched"] < CACHE_SECONDS:
        return
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(
                "https://api.abuseipdb.com/api/v2/check",
                params={"ipAddress": ip, "maxAgeInDays": 90},
                headers={"Key": api_key, "Accept": "application/json"},
            )
            r.raise_for_status()
            d: dict[str, Any] = r.json().get("data", {})
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("AbuseIPDB lookup for %s failed: %s", ip, exc)
        return
    store.save_intel(
        ip,
        {
            "score": d.get("abuseConfidenceScore"),
            "reports": d.get("totalReports"),
            "usage": d.get("usageType"),
            "isp": d.get("isp"),
            "domain": d.get("domain"),
        },
    )
