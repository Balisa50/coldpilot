"""
In-memory pub/sub for SSE streaming. The orchestrator publishes pipeline events,
and the SSE endpoint subscribes per-campaign to stream them to the dashboard.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict


_subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)


def subscribe(campaign_id: str) -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue()
    _subscribers[campaign_id].append(queue)
    return queue


def unsubscribe(campaign_id: str, queue: asyncio.Queue) -> None:
    if campaign_id in _subscribers:
        _subscribers[campaign_id] = [
            q for q in _subscribers[campaign_id] if q is not queue
        ]
        if not _subscribers[campaign_id]:
            del _subscribers[campaign_id]


async def publish(campaign_id: str, event: dict) -> None:
    for queue in _subscribers.get(campaign_id, []):
        await queue.put(event)
