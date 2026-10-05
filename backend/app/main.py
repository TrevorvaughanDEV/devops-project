"""HTTP API, live WebSocket feed and static frontend, plus the honeypot sensor.

Everything runs in one process and one event loop, so a login attempt goes from
the SSH handshake to every open browser without a message broker in between.
Run it with a single worker: the live feed lives in memory.
"""

import asyncio
import contextlib
import ipaddress
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse

from . import config, intel
from .db import EVENT_COLUMNS, TOP_FIELDS, Store
from .geo import GeoLookup
from .live import Hub
from .sensor import Sensor, load_host_keys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("whos-knocking")

PUBLIC_FIELDS = [c.strip() for c in EVENT_COLUMNS.split(",")]


def create_app(
    settings: config.Settings | None = None, start_sensor: bool | None = None
) -> FastAPI:
    settings = settings or config.load()
    run_sensor = settings.sensor_enabled if start_sensor is None else start_sensor

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store = Store(settings.database_path)
        geo = GeoLookup(settings.geo_city_db, settings.geo_asn_db)
        hub = Hub()
        app.state.store, app.state.geo, app.state.hub = store, geo, hub
        app.state.started = time.time()

        def record(event: dict[str, Any]) -> None:
            event.update(geo.lookup(event["ip"]))
            event["id"] = store.add_attempt(event)
            hub.publish({k: event.get(k) for k in PUBLIC_FIELDS})

        app.state.record = record
        sensor = Sensor(record, settings.max_connections, settings.max_connections_per_ip)
        app.state.sensor = sensor
        if run_sensor:
            await sensor.start(
                settings.sensor_port, load_host_keys(settings.data_dir), settings.sensor_banner
            )

        async def housekeeping() -> None:
            while True:
                removed = store.prune(settings.retention_days)
                if removed:
                    logger.info(
                        "Pruned %d attempts older than %d days", removed, settings.retention_days
                    )
                await asyncio.sleep(6 * 3600)

        task = asyncio.create_task(housekeeping())
        try:
            yield
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            await sensor.stop()
            store.close()

    app = FastAPI(title="Who's Knocking", lifespan=lifespan, docs_url="/api/docs", redoc_url=None)

    # --- health and metadata -------------------------------------------------

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/meta")
    def meta() -> dict[str, Any]:
        return {
            "server": {
                "label": settings.server_label,
                "lat": settings.server_lat,
                "lon": settings.server_lon,
            },
            "port": settings.public_port,
            "sensor_running": app.state.sensor.port is not None,
            "geo_enabled": app.state.geo.enabled,
            "intel_enabled": bool(settings.abuseipdb_key),
            "started": app.state.started,
            "viewers": app.state.hub.clients,
        }

    # --- statistics ------------------------------------------------------------

    @app.get("/api/summary")
    def summary(hours: int = Query(24, ge=1, le=720)) -> dict[str, Any]:
        return app.state.store.summary(hours)

    @app.get("/api/recent")
    def recent(limit: int = Query(50, ge=1, le=200)) -> list[dict[str, Any]]:
        return app.state.store.recent(limit)

    @app.get("/api/top/{kind}")
    def top(
        kind: str,
        hours: int = Query(24, ge=1, le=720),
        limit: int = Query(10, ge=1, le=50),
    ) -> list[dict[str, Any]]:
        if kind not in TOP_FIELDS:
            raise HTTPException(404, f"Unknown list. Use one of: {', '.join(TOP_FIELDS)}")
        return app.state.store.top(kind, hours, limit)

    @app.get("/api/map")
    def map_points(hours: int = Query(24, ge=1, le=720)) -> list[dict[str, Any]]:
        return app.state.store.map_points(hours)

    @app.get("/api/timeline")
    def timeline(hours: int = Query(48, ge=1, le=720)) -> list[dict[str, Any]]:
        return app.state.store.timeline(hours)

    @app.get("/api/heatmap")
    def heatmap(days: int = Query(30, ge=1, le=90)) -> list[dict[str, Any]]:
        return app.state.store.heatmap(days)

    @app.get("/api/ip/{ip}")
    async def ip_detail(ip: str) -> dict[str, Any]:
        try:
            ip = str(ipaddress.ip_address(ip))
        except ValueError as exc:
            raise HTTPException(400, "That isn't a valid IP address.") from exc
        if app.state.store.ip_detail(ip) is None:
            raise HTTPException(404, "This address hasn't tried to log in.")
        await intel.enrich(app.state.store, ip, settings.abuseipdb_key)
        return app.state.store.ip_detail(ip)

    # --- live feed -------------------------------------------------------------

    @app.websocket("/api/live")
    async def live(ws: WebSocket) -> None:
        await ws.accept()
        q = app.state.hub.subscribe()
        if q is None:
            await ws.close(code=1013, reason="Too many viewers, try again shortly")
            return
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=25)
                    await ws.send_json({"type": "attempt", "data": event})
                except TimeoutError:
                    await ws.send_json({"type": "ping"})  # keeps proxies from idling us out
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            app.state.hub.unsubscribe(q)

    # --- frontend --------------------------------------------------------------

    static = Path(settings.static_dir)
    index = static / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        if path.startswith("api/"):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        target = (static / path).resolve()
        if path and target.is_file() and static.resolve() in target.parents:
            return FileResponse(target)
        if index.is_file():
            return FileResponse(index)
        return JSONResponse({"detail": "Frontend not built"}, status_code=404)

    return app


app = create_app()
