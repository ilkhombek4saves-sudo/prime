from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from typing import Any


class InMemoryEventBus:
    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self) -> tuple[str, asyncio.Queue]:
        subscription_id = str(uuid.uuid4())
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        async with self._lock:
            self._queues[subscription_id] = queue
        return subscription_id, queue

    async def unsubscribe(self, subscription_id: str) -> None:
        async with self._lock:
            self._queues.pop(subscription_id, None)

    async def publish(self, event_name: str, data: dict[str, Any]) -> None:
        async with self._lock:
            queues = list(self._queues.values())
        payload = {"event": event_name, "data": data}
        for queue in queues:
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(payload)

    def publish_nowait(self, event_name: str, data: dict[str, Any]) -> None:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.publish(event_name, data))
        except RuntimeError:
            # Out of event loop context; best effort.
            return


_EVENT_BUS = InMemoryEventBus()


def get_event_bus() -> InMemoryEventBus:
    return _EVENT_BUS
