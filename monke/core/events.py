"""Simple in-process async event bus for Monke structured events.

Events are dictionaries with at least keys:
- type: str (e.g., 'flow_started', 'step_started', 'step_completed', 'step_failed', 'flow_completed')
- run_id: str (identifier for the current test run)
- ts: float (unix timestamp)

Usage:
  from monke.core import events
  await events.publish({"type": "step_started", "run_id": "...", ...})
  q = events.subscribe()
  ... await q.get()  # receives event dicts
  events.unsubscribe(q)
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Set


class _EventBus:
    def __init__(self) -> None:
        self._subscribers: Set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    async def publish(self, event: Dict[str, Any]) -> None:
        # Fan-out non-blocking; drop if queue full
        dead = []
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except Exception:
                dead.append(q)
        for q in dead:
            self._subscribers.discard(q)


bus = _EventBus()


def subscribe() -> asyncio.Queue:
    return bus.subscribe()


def unsubscribe(queue: asyncio.Queue) -> None:
    bus.unsubscribe(queue)


async def publish(event: Dict[str, Any]) -> None:
    await bus.publish(event)
