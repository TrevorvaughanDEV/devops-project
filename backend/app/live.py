"""Fan-out of new attempts to every open WebSocket."""

import asyncio
from typing import Any


class Hub:
    def __init__(self, max_clients: int = 300, queue_size: int = 200):
        self._queues: set[asyncio.Queue] = set()
        self.max_clients = max_clients
        self.queue_size = queue_size

    @property
    def clients(self) -> int:
        return len(self._queues)

    def subscribe(self) -> asyncio.Queue | None:
        if len(self._queues) >= self.max_clients:
            return None
        q: asyncio.Queue = asyncio.Queue(maxsize=self.queue_size)
        self._queues.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._queues.discard(q)

    def publish(self, event: dict[str, Any], kind: str = "attempt") -> None:
        message = {"type": kind, "data": event}
        for q in list(self._queues):
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                # A slow browser just misses events rather than holding up the sensor.
                pass
